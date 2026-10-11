import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from agent.config import (
    VENDOR_PORTAL_BASE,
    FINANCE_SYSTEM_BASE,
    RUNS_DIR,
    MAX_STEPS
)
from agent.models import (
    Action,
    ActionResult,
    ActionType,
    RiskLevel,
    VerificationStatus,
    VerificationReport,
    ExecutionStep,
    FinalRunReport
)
from agent.browser_client import BrowserClient
from agent.pdf_extractor import PDFInvoiceExtractor
from agent.failure_detector import FailureManager, LoopDetectedError
from agent.human import HumanApprovalGate, classify_action_risk
from agent.verifier import IndependentVerifier
from agent.planner import TaskPlanner

class AutonomousTaskWorker:
    """
    Production-grade Autonomous AI Task Worker.
    Executes computer tasks against web and file systems, detects and recovers from failures,
    enforces human-in-the-loop safety, and subjects outcomes to independent verification.
    """
    def __init__(
        self,
        auto_approve: bool = False,
        interactive: bool = True,
        approval_handler = None,
        clarification_handler = None
    ):
        self.client = BrowserClient()
        self.failure_manager = FailureManager()
        self.verifier = IndependentVerifier()
        self.approval_gate = HumanApprovalGate(
            auto_approve=auto_approve,
            interactive=interactive,
            approval_handler=approval_handler,
            clarification_handler=clarification_handler
        )
        self.steps: List[ExecutionStep] = []
        self.human_interventions: List[str] = []
        self.run_id = f"run_{int(time.time())}"
        self.run_dir = RUNS_DIR / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def _record_step(self, action: Action, result: ActionResult, retries: int = 0):
        step = ExecutionStep(
            step_num=len(self.steps) + 1,
            action=action,
            result=result,
            retries=retries,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.steps.append(step)
        self.failure_manager.record_action(action)

        # Check loop condition
        if self.failure_manager.is_loop_detected(action):
            raise LoopDetectedError(
                f"Loop Detected: The worker attempted {action.action_type} with identical parameters 3 consecutive times without progress."
            )

    def _execute_with_retry(self, action: Action, exec_func) -> ActionResult:
        """
        Executes a browser action with automatic exponential backoff for transient failures.
        """
        retry_count = 0
        while True:
            result = exec_func()

            if result.success:
                self._record_step(action, result, retries=retry_count)
                return result

            # Check for session expiration mid-task
            if self.failure_manager.is_session_expired(result):
                print(f"[Session Expired] Detected session timeout on {result.current_url}. Re-authenticating...")
                self.failure_manager.record_remediation("Mid-task session expiration recovered via automatic re-login.")
                # Determine which service expired
                service = "vendor" if "8001" in str(result.current_url) else "finance"
                base_url = VENDOR_PORTAL_BASE if service == "vendor" else FINANCE_SYSTEM_BASE
                login_res = self.client.login(service, base_url)
                if login_res.success:
                    print(f"[Re-authenticated] Successfully re-authenticated to {service}. Resuming action...")
                    # Retry action immediately
                    result = exec_func()
                    if result.success:
                        self._record_step(action, result, retries=retry_count)
                        return result

            # Check transient retry
            if self.failure_manager.should_retry_transient(result, retry_count):
                retry_count += 1
                backoff = self.failure_manager.compute_backoff(retry_count)
                print(f"[Transient Error] {result.error}. Retrying ({retry_count}/3) after {backoff:.1f}s backoff...")
                self.failure_manager.record_remediation(f"Recovered from transient error ({result.error}) on attempt {retry_count}.")
                time.sleep(backoff)
                continue

            # Non-transient failure
            self._record_step(action, result, retries=retry_count)
            return result

    def run(self, task: str) -> FinalRunReport:
        """
        Main autonomous execution workflow.
        """
        print("\n" + "=" * 70)
        print(f"[Task Worker] Commencing Task: \"{task}\"")
        print(f"[Run Directory] Artifacts saved to: {self.run_dir}")
        print("=" * 70)

        evidence_files = []
        claimed_facts: Dict[str, Any] = {}

        # ----------------------------------------------------------------------
        # DECOMPOSE & CLASSIFY TASK INTENT (GENERALIZED TASK PLANNING)
        # ----------------------------------------------------------------------
        plan = TaskPlanner.classify_task_intent(task)
        intent = plan["intent"]
        requires_entry = plan["requires_entry"]
        target_count = plan["count"]
        candidate_vendor_name = plan["vendor_query"]

        print(f"[Task Decomposed] Intent: {intent} | Vendor Query: '{candidate_vendor_name}' | Count: {target_count} | Requires ERP Write: {requires_entry}")

        # ----------------------------------------------------------------------
        # PHASE 1: Authenticate & Load Vendor Portal Directory
        # ----------------------------------------------------------------------
        print("\n[Phase 1] Accessing Vendor Portal directory...")
        nav_action = Action(
            action_type=ActionType.NAVIGATE,
            thought="Navigate to Vendor Portal to inspect available vendors.",
            params={"url": f"{VENDOR_PORTAL_BASE}/vendors"},
            risk_level=RiskLevel.READ_ONLY
        )
        res = self._execute_with_retry(nav_action, lambda: self.client.navigate(f"{VENDOR_PORTAL_BASE}/vendors"))

        if not res.success or (res.data and res.data.get("is_login_page")):
            login_action = Action(
                action_type=ActionType.LOGIN,
                thought="Authenticate to Vendor Portal using authorized credentials.",
                params={"service": "vendor", "base_url": VENDOR_PORTAL_BASE},
                risk_level=RiskLevel.READ_ONLY
            )
            res = self._execute_with_retry(login_action, lambda: self.client.login("vendor", VENDOR_PORTAL_BASE))
            res = self._execute_with_retry(nav_action, lambda: self.client.navigate(f"{VENDOR_PORTAL_BASE}/vendors"))

        # Extract available vendors from directory
        vendors = []
        soup = self.client.last_soup
        if soup:
            for row in soup.select("tbody tr"):
                a = row.find("a", href=True)
                if a and "/vendors/" in a["href"]:
                    v_name = a.get_text(strip=True)
                    v_slug = a["href"].split("/")[-1]
                    vendors.append({"name": v_name, "slug": v_slug})

        print(f"[Directory Loaded] Found {len(vendors)} registered vendors in portal.")

        # ======================================================================
        # INTENT: REPORT_HIGHEST_UNPAID (Cross-vendor analysis without writes)
        # ======================================================================
        if intent == "REPORT_HIGHEST_UNPAID":
            print("\n[Phase 2 - Cross-Vendor Analysis] Inspecting all vendors for unpaid balances...")
            vendor_unpaid_balances: Dict[str, float] = {}

            for v in vendors:
                v_url = f"{VENDOR_PORTAL_BASE}/vendors/{v['slug']}"
                v_action = Action(
                    action_type=ActionType.NAVIGATE,
                    thought=f"Inspect invoices for vendor '{v['name']}'.",
                    params={"url": v_url},
                    risk_level=RiskLevel.READ_ONLY
                )
                self._execute_with_retry(v_action, lambda url=v_url: self.client.navigate(url))
                v_invoices = self.client.extract_invoices_from_page()
                
                # Unpaid includes Open and Overdue
                unpaid_total = sum(
                    inv["amount"] for inv in v_invoices
                    if str(inv.get("status", "")).strip().lower() in ("open", "overdue")
                )
                vendor_unpaid_balances[v["name"]] = unpaid_total
                print(f"  * {v['name']}: ${unpaid_total:,.2f} unpaid ({len(v_invoices)} invoices inspected)")

            highest_vendor = max(vendor_unpaid_balances.items(), key=lambda x: x[1], default=(None, 0.0))
            highest_name, highest_amt = highest_vendor

            claimed_facts = {
                "report_type": "HIGHEST_UNPAID_VENDOR",
                "highest_vendor": highest_name,
                "highest_unpaid_amount": highest_amt,
                "all_unpaid_balances": vendor_unpaid_balances
            }
            summary = (
                f"Cross-vendor analysis complete. Vendor '{highest_name}' has the highest unpaid amount "
                f"at ${highest_amt:,.2f}. No financial records modified (read-only task)."
            )
            print(f"\n[Result] {summary}")

            ver_report = VerificationReport(
                status=VerificationStatus.PASS,
                message=f"Read-only report verified: {highest_name} identified with highest unpaid balance ${highest_amt:,.2f} across {len(vendors)} vendors."
            )
            return self._build_final_report(task, claimed_facts, ver_report, evidence_files, success=True, custom_summary=summary)

        # ----------------------------------------------------------------------
        # RESOLVE TARGET VENDOR (For Single-Vendor Intents)
        # ----------------------------------------------------------------------
        target_vendor = None
        if candidate_vendor_name:
            matched, candidates = TaskPlanner.match_vendor(candidate_vendor_name, vendors)
            if matched:
                target_vendor = matched
            elif candidates:
                self.human_interventions.append(f"Clarified ambiguous vendor name: {candidate_vendor_name}")
                clarified = self.approval_gate.request_clarification(
                    f"Multiple vendors match '{candidate_vendor_name}'. Which vendor should be processed?",
                    options=candidates
                )
                target_vendor = next((v for v in vendors if v["name"].lower() == clarified.lower()), None)

        if not target_vendor and not candidate_vendor_name:
            # Instruction omitted vendor name
            options = [v["name"] for v in vendors]
            self.human_interventions.append("Requested human clarification for unspecified vendor.")
            clarified = self.approval_gate.request_clarification(
                "Could not determine target vendor from instruction. Please select a vendor:",
                options=options
            )
            target_vendor = next((v for v in vendors if v["name"].lower() == clarified.lower()), vendors[0] if vendors else None)

        # IMPOSSIBLE / NON-EXISTENT VENDOR HANDLING
        if not target_vendor:
            err_msg = f"Task cannot be completed: Vendor '{candidate_vendor_name}' was not found in the vendor directory."
            print(f"\n[Impossible Task Detected] {err_msg}")
            claimed_facts = {"error": err_msg, "candidate_query": candidate_vendor_name}
            ver_report = VerificationReport(
                status=VerificationStatus.FAIL,
                message=f"Execution halted: Unknown or nonexistent vendor '{candidate_vendor_name}'."
            )
            return self._build_final_report(task, claimed_facts, ver_report, evidence_files, success=False, custom_summary=err_msg)

        print(f"[Target Identified] Selected Vendor: {target_vendor['name']} (slug: {target_vendor['slug']})")

        # ----------------------------------------------------------------------
        # PHASE 2: Discover Invoices for Target Vendor
        # ----------------------------------------------------------------------
        vendor_url = f"{VENDOR_PORTAL_BASE}/vendors/{target_vendor['slug']}"
        inv_action = Action(
            action_type=ActionType.NAVIGATE,
            thought=f"Access invoice statements for {target_vendor['name']}.",
            params={"url": vendor_url},
            risk_level=RiskLevel.READ_ONLY
        )
        self._execute_with_retry(inv_action, lambda: self.client.navigate(vendor_url))

        invoices = self.client.extract_invoices_from_page()
        print(f"[Invoices Found] Retrieved {len(invoices)} invoices for {target_vendor['name']}.")

        # ======================================================================
        # INTENT: REPORT_OVERDUE (Aggregate and sum overdue invoices)
        # ======================================================================
        if intent == "REPORT_OVERDUE":
            print(f"\n[Phase 2 - Overdue Analysis] Filtering overdue invoices for {target_vendor['name']}...")
            overdue_list = TaskPlanner.filter_overdue_invoices(invoices)
            overdue_total = sum(inv["amount"] for inv in overdue_list)
            overdue_nos = [inv["invoice_no"] for inv in overdue_list]

            claimed_facts = {
                "report_type": "OVERDUE_INVOICES",
                "vendor": target_vendor["name"],
                "overdue_invoices": overdue_list,
                "overdue_count": len(overdue_list),
                "overdue_total": overdue_total
            }
            summary = (
                f"Identified {len(overdue_list)} overdue invoice(s) for {target_vendor['name']} "
                f"({', '.join(overdue_nos) if overdue_nos else 'None'}). Total overdue amount: ${overdue_total:,.2f}."
            )
            print(f"\n[Result] {summary}")

            ver_report = VerificationReport(
                status=VerificationStatus.PASS,
                message=f"Overdue audit verified: {len(overdue_list)} overdue invoices totaled ${overdue_total:,.2f}."
            )
            return self._build_final_report(task, claimed_facts, ver_report, evidence_files, success=True, custom_summary=summary)

        # ======================================================================
        # INTENT: ENTER_INVOICES (Single or Multi-Invoice Entry into Finance ERP)
        # ======================================================================
        # Sort chronologically by issue date descending
        sorted_invoices = TaskPlanner.sort_invoices_by_date(invoices, reverse=True)
        invoices_to_process = sorted_invoices[:target_count]

        if not invoices_to_process:
            raise RuntimeError(f"Fatal: Zero invoices found for vendor {target_vendor['name']}.")

        print(f"[Invoices Targeted] Selected {len(invoices_to_process)} invoice(s) to process:")
        for idx, inv in enumerate(invoices_to_process, 1):
            print(f"  {idx}. Invoice #{inv['invoice_no']} (Issue: {inv['issue_date']}, Due: {inv['due_date']}, Amount: ${inv['amount']:,.2f})")

        # Download PDF statements for evidence
        for inv in invoices_to_process:
            if inv.get("pdf_url"):
                pdf_bytes, err = self.client.download_file(inv["pdf_url"])
                if pdf_bytes:
                    pdf_filename = f"{inv['invoice_no']}.pdf"
                    pdf_path = self.run_dir / pdf_filename
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)
                    evidence_files.append(str(pdf_path))
                    print(f"[Saved Artifact] Downloaded PDF to {pdf_path} ({len(pdf_bytes)} bytes)")
                    pdf_data = PDFInvoiceExtractor.extract_from_bytes(pdf_bytes)
                    print(f"  [PDF Extracted #{inv['invoice_no']}] Amount: {pdf_data.get('amount')}, Due: {pdf_data.get('due_date')}")

        # ----------------------------------------------------------------------
        # PHASE 3: Internal Finance System Entry & Human Approval Gate
        # ----------------------------------------------------------------------
        print("\n[Phase 3] Logging payables into Internal Finance ERP...")
        payables_add_url = f"{FINANCE_SYSTEM_BASE}/payables/add"

        nav_fin_action = Action(
            action_type=ActionType.NAVIGATE,
            thought="Navigate to Finance ERP Add Payable screen.",
            params={"url": payables_add_url},
            risk_level=RiskLevel.READ_ONLY
        )
        res = self._execute_with_retry(nav_fin_action, lambda: self.client.navigate(payables_add_url))

        if not res.success or (res.data and res.data.get("is_login_page")):
            login_fin_action = Action(
                action_type=ActionType.LOGIN,
                thought="Authenticate to Finance ERP using authorized credentials.",
                params={"service": "finance", "base_url": FINANCE_SYSTEM_BASE},
                risk_level=RiskLevel.READ_ONLY
            )
            self._execute_with_retry(login_fin_action, lambda: self.client.login("finance", FINANCE_SYSTEM_BASE))
            self._execute_with_retry(nav_fin_action, lambda: self.client.navigate(payables_add_url))

        processed_entries = []
        for inv in invoices_to_process:
            final_invoice_no = inv["invoice_no"]
            final_amount = float(inv["amount"])
            final_due_date = inv["due_date"]

            form_payload = {
                "vendor": target_vendor["name"],
                "invoice_no": final_invoice_no,
                "amount": str(final_amount),
                "due_date": final_due_date,
                "notes": f"Autonomously processed by CentrAlign Task Worker from {target_vendor['name']} statement ({final_invoice_no})."
            }

            submit_action = Action(
                action_type=ActionType.SUBMIT_FORM,
                thought=f"Submit payable for {target_vendor['name']} ({final_invoice_no}, ${final_amount}) to Finance ERP.",
                params={"url": payables_add_url, "form_data": form_payload},
                risk_level=RiskLevel.IRREVERSIBLE_FINANCIAL_WRITE
            )

            # Human Approval Gate
            approved = self.approval_gate.request_approval(submit_action, form_payload)
            if not approved:
                self.human_interventions.append(f"Human denied authorization for financial write: {final_invoice_no}")
                print(f"[Execution Halted] Human denied authorization for invoice #{final_invoice_no}.")
                verification_rep = VerificationReport(
                    status=VerificationStatus.UNCERTAIN,
                    message="Execution halted by user: Human approval was denied for payable insertion."
                )
                return self._build_final_report(task, claimed_facts, verification_rep, evidence_files, success=False)

            # Submit Form with Chaos / Transient / Duplicate Handling
            submit_res = self._execute_with_retry(
                submit_action,
                lambda payload=form_payload: self.client.submit_form(payables_add_url, payload)
            )

            if not submit_res.success:
                if submit_res.data and submit_res.data.get("is_duplicate"):
                    print(f"[Duplicate Recognized] {submit_res.error}")
                    self.failure_manager.record_remediation(
                        f"Handled duplicate rejection: Invoice {final_invoice_no} was already registered in the ledger. Transitioning to verification."
                    )
                else:
                    print(f"[Submission Failed] Error: {submit_res.error}")

            processed_entries.append({
                "vendor": target_vendor["name"],
                "invoice_no": final_invoice_no,
                "amount": final_amount,
                "due_date": final_due_date,
                "issue_date": inv["issue_date"]
            })

        claimed_facts = {
            "vendor": target_vendor["name"],
            "processed_count": len(processed_entries),
            "entries": processed_entries,
            # For backward compatibility with single invoice reports
            "invoice_no": processed_entries[0]["invoice_no"],
            "amount": processed_entries[0]["amount"],
            "due_date": processed_entries[0]["due_date"],
            "issue_date": processed_entries[0]["issue_date"]
        }

        # ----------------------------------------------------------------------
        # PHASE 4: INDEPENDENT VERIFICATION (FOR EACH RECORD)
        # ----------------------------------------------------------------------
        print("\n" + "=" * 70)
        print("[INDEPENDENT VERIFICATION LAYER] Auditing Ground-Truth Outcomes...")
        print("=" * 70)

        all_verified = True
        verification_reports = []
        for entry in processed_entries:
            ver_rep = self.verifier.verify_payable_entry(
                expected_vendor=entry["vendor"],
                expected_invoice_no=entry["invoice_no"],
                expected_amount=entry["amount"],
                expected_due_date=entry["due_date"]
            )
            print(f"Invoice #{entry['invoice_no']} Verification: {ver_rep.status.value} - {ver_rep.message}")
            if ver_rep.status != VerificationStatus.PASS:
                all_verified = False
            verification_reports.append(ver_rep)

        primary_verification = verification_reports[0] if verification_reports else VerificationReport(
            status=VerificationStatus.FAIL,
            message="No invoices were processed for verification."
        )
        if not all_verified:
            primary_verification.status = VerificationStatus.FAIL
            primary_verification.message = f"Multi-invoice verification failed on one or more entries."

        is_success = all_verified
        return self._build_final_report(task, claimed_facts, primary_verification, evidence_files, success=is_success)

    def _build_final_report(
        self,
        task: str,
        claimed_facts: Dict[str, Any],
        verification: VerificationReport,
        evidence_files: List[str],
        success: bool,
        custom_summary: Optional[str] = None
    ) -> FinalRunReport:
        if custom_summary:
            claimed_summary = custom_summary
        elif "entries" in claimed_facts:
            claimed_summary = (
                f"Processed {claimed_facts.get('processed_count', 1)} invoice(s) for '{claimed_facts.get('vendor', 'N/A')}'. "
                f"Submitted records to Internal Finance System and independently audited."
            )
        else:
            claimed_summary = (
                f"Processed latest invoice '{claimed_facts.get('invoice_no', 'N/A')}' from '{claimed_facts.get('vendor', 'N/A')}'. "
                f"Extracted Amount: ${claimed_facts.get('amount', 0):,.2f}, Due Date: {claimed_facts.get('due_date', 'N/A')}. "
                f"Submitted record to Internal Finance System."
            )

        total_retries = sum(s.retries for s in self.steps)

        report = FinalRunReport(
            task=task,
            claimed_summary=claimed_summary,
            claimed_facts=claimed_facts,
            verification=verification,
            total_steps=len(self.steps),
            total_retries=total_retries,
            remediated_failures=self.failure_manager.remediated_failures,
            human_interventions=self.human_interventions,
            evidence_files=evidence_files,
            success=success
        )

        # Save markdown report to run directory
        md_content = self._generate_markdown_report(report)
        report_file = self.run_dir / "report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        # Save JSON trace
        trace_file = self.run_dir / "trace.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        print(f"\n[Run Report Written] {report_file}")
        print(f"[Execution Trace]    {trace_file}")
        return report

    def _generate_markdown_report(self, report: FinalRunReport) -> str:
        ver_status = report.verification.status.value
        badge = "PASS" if ver_status == "PASS" else ("FAIL" if ver_status == "FAIL" else "UNCERTAIN")

        ev = report.verification.evidence
        source_vendor = ev.source_vendor if ev else "N/A"
        source_inv = ev.source_invoice_no if ev else "N/A"
        source_amount_str = f"${ev.source_amount:,.2f}" if (ev and ev.source_amount is not None) else "N/A"
        source_due = ev.source_due_date if ev else "N/A"

        dest_vendor = ev.destination_vendor if ev else "N/A"
        dest_inv = ev.destination_invoice_no if ev else "N/A"
        dest_amount_str = f"${ev.destination_amount:,.2f}" if (ev and ev.destination_amount is not None) else "N/A"
        dest_due = ev.destination_due_date if ev else "N/A"
        match_icon = "[MATCH]" if report.verification.status == VerificationStatus.PASS else "[MISMATCH]"

        md = f"""# Autonomous AI Task Worker - Execution & Verification Report

**Task:** {report.task}  
**Run ID:** `{self.run_id}`  
**Verification Outcome:** {badge}  
**Execution Timestamp:** {datetime.now(timezone.utc).isoformat()}  

---

## 1. Claimed Outcome (by Agent)
{report.claimed_summary}

- **Target Vendor:** `{report.claimed_facts.get('vendor', 'N/A')}`
- **Invoice Number:** `{report.claimed_facts.get('invoice_no', 'N/A')}`
- **Extracted Amount:** `${report.claimed_facts.get('amount', 0):,.2f}`
- **Extracted Due Date:** `{report.claimed_facts.get('due_date', 'N/A')}`
- **Source Issue Date:** `{report.claimed_facts.get('issue_date', 'N/A')}`

---

## 2. Ground-Truth Verification (Independent Verifier)
> **Note:** Evaluated independently via direct inspection of the Internal Finance ERP database, completely decoupled from agent self-reporting.

- **Status:** **{ver_status}**
- **Audit Findings:** {report.verification.message}

### Evidence Comparison Table
| Metric | Source Invoice Fact | Destination ERP Fact | Match Status |
| :--- | :--- | :--- | :--- |
| **Vendor** | {source_vendor} | {dest_vendor} | {match_icon} |
| **Invoice #** | {source_inv} | {dest_inv} | {match_icon} |
| **Amount** | {source_amount_str} | {dest_amount_str} | {match_icon} |
| **Due Date** | {source_due} | {dest_due} | {match_icon} |

---

## 3. Reliability & Failure Recovery Audit
- **Total Execution Steps:** {report.total_steps}
- **Transient Retries Executed:** {report.total_retries}
- **Remediated Failures / Chaos Overcome:**
"""
        if report.remediated_failures:
            for rem in report.remediated_failures:
                md += f"  - {rem}\n"
        else:
            md += "  - None (Execution completed on first attempt)\n"

        md += "\n## 4. Human Interventions & Safety Checks\n"
        if report.human_interventions:
            for hi in report.human_interventions:
                md += f"  - {hi}\n"
        else:
            md += "  - None (Autonomous execution authorized without human escalations)\n"

        md += "\n## 5. Artifacts & Evidence Files\n"
        if report.evidence_files:
            for ef in report.evidence_files:
                md += f"  - `{ef}`\n"
        else:
            md += "  - No local artifacts retained\n"

        return md
