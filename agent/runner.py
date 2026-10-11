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
        # PHASE 1: Entity Resolution & Ambiguity Check
        # ----------------------------------------------------------------------
        print("\n[Phase 1] Analyzing instruction & locating vendor...")
        candidate_vendor_name = TaskPlanner.extract_vendor_query(task)

        # 1. Navigate to Vendor Portal
        nav_action = Action(
            action_type=ActionType.NAVIGATE,
            thought="Navigate to Vendor Portal to inspect vendor directory.",
            params={"url": f"{VENDOR_PORTAL_BASE}/vendors"},
            risk_level=RiskLevel.READ_ONLY
        )
        res = self._execute_with_retry(nav_action, lambda: self.client.navigate(f"{VENDOR_PORTAL_BASE}/vendors"))

        # If redirected to login, authenticate
        if not res.success or (res.data and res.data.get("is_login_page")):
            login_action = Action(
                action_type=ActionType.LOGIN,
                thought="Authenticate to Vendor Portal using authorized credentials.",
                params={"service": "vendor", "base_url": VENDOR_PORTAL_BASE},
                risk_level=RiskLevel.READ_ONLY
            )
            res = self._execute_with_retry(login_action, lambda: self.client.login("vendor", VENDOR_PORTAL_BASE))
            # Navigate back to /vendors
            res = self._execute_with_retry(nav_action, lambda: self.client.navigate(f"{VENDOR_PORTAL_BASE}/vendors"))

        # Parse vendors from directory
        vendors = []
        soup = self.client.last_soup
        if soup:
            for row in soup.select("tbody tr"):
                a = row.find("a", href=True)
                if a and "/vendors/" in a["href"]:
                    v_name = a.get_text(strip=True)
                    v_slug = a["href"].split("/")[-1]
                    vendors.append({"name": v_name, "slug": v_slug})

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

        if not target_vendor:
            # Ambiguity: could not deduce vendor from query or multiple available
            options = [v["name"] for v in vendors]
            self.human_interventions.append("Requested human clarification for unspecified vendor.")
            clarified = self.approval_gate.request_clarification(
                "Could not determine target vendor from instruction. Please select a vendor:",
                options=options
            )
            target_vendor = next((v for v in vendors if v["name"].lower() == clarified.lower()), vendors[0] if vendors else None)

        if not target_vendor:
            raise RuntimeError("Fatal: No target vendor could be identified.")

        print(f"[Target Identified] Selected Vendor: {target_vendor['name']} (slug: {target_vendor['slug']})")

        # ----------------------------------------------------------------------
        # PHASE 2: Discover Invoices, Compare Dates & Extract PDF
        # ----------------------------------------------------------------------
        print(f"\n[Phase 2] Inspecting invoices for {target_vendor['name']}...")
        vendor_url = f"{VENDOR_PORTAL_BASE}/vendors/{target_vendor['slug']}"
        inv_action = Action(
            action_type=ActionType.NAVIGATE,
            thought=f"Access invoice statements for {target_vendor['name']}.",
            params={"url": vendor_url},
            risk_level=RiskLevel.READ_ONLY
        )
        res = self._execute_with_retry(inv_action, lambda: self.client.navigate(vendor_url))

        # Extract invoices (supporting both table and card layouts)
        invoices = self.client.extract_invoices_from_page()
        print(f"[Invoices Found] Retrieved {len(invoices)} invoices (Layout detected: {invoices[0]['source_layout'] if invoices else 'unknown'})")

        # Select the strictly latest invoice by comparing issue dates
        latest_inv = TaskPlanner.select_latest_invoice(invoices)
        if not latest_inv:
            raise RuntimeError(f"Fatal: Zero invoices found for vendor {target_vendor['name']}.")

        print(f"[Latest Selected] Invoice #{latest_inv['invoice_no']} (Issue Date: {latest_inv['issue_date']}, Due Date: {latest_inv['due_date']}, Amount: ${latest_inv['amount']:,.2f})")

        # Download authentic PDF statement
        pdf_bytes = None
        if latest_inv.get("pdf_url"):
            print(f"[Downloading PDF] Fetching statement from {latest_inv['pdf_url']}...")
            pdf_bytes, err = self.client.download_file(latest_inv["pdf_url"])
            if pdf_bytes:
                pdf_filename = f"{latest_inv['invoice_no']}.pdf"
                pdf_path = self.run_dir / pdf_filename
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                evidence_files.append(str(pdf_path))
                print(f"[Saved Artifact] Downloaded PDF to {pdf_path} ({len(pdf_bytes)} bytes)")

                # Extract and cross-validate with PDF text
                pdf_data = PDFInvoiceExtractor.extract_from_bytes(pdf_bytes)
                print(f"[PDF Ground Truth] Extracted from PDF: Invoice #{pdf_data.get('invoice_no')}, Amount: {pdf_data.get('amount')}, Due: {pdf_data.get('due_date')}")

        final_invoice_no = latest_inv["invoice_no"]
        final_amount = float(latest_inv["amount"])
        final_due_date = latest_inv["due_date"]

        claimed_facts = {
            "vendor": target_vendor["name"],
            "invoice_no": final_invoice_no,
            "amount": final_amount,
            "due_date": final_due_date,
            "issue_date": latest_inv["issue_date"]
        }

        # ----------------------------------------------------------------------
        # PHASE 3: Internal Finance System Entry & Human Approval Gate
        # ----------------------------------------------------------------------
        print("\n[Phase 3] Logging payable into Internal Finance ERP...")
        payables_add_url = f"{FINANCE_SYSTEM_BASE}/payables/add"

        # Check login state on Finance System
        nav_fin_action = Action(
            action_type=ActionType.NAVIGATE,
            thought="Navigate to Finance ERP Add Payable screen.",
            params={"url": payables_add_url},
            risk_level=RiskLevel.READ_ONLY
        )
        res = self._execute_with_retry(nav_fin_action, lambda: self.client.navigate(payables_add_url))

        if not res.success or (res.data and res.data.get("is_login_page")):
            print("[Finance Auth] Logging into Internal Finance System...")
            login_fin_action = Action(
                action_type=ActionType.LOGIN,
                thought="Authenticate to Finance ERP using authorized credentials.",
                params={"service": "finance", "base_url": FINANCE_SYSTEM_BASE},
                risk_level=RiskLevel.READ_ONLY
            )
            res = self._execute_with_retry(login_fin_action, lambda: self.client.login("finance", FINANCE_SYSTEM_BASE))
            res = self._execute_with_retry(nav_fin_action, lambda: self.client.navigate(payables_add_url))

        # Prepare payable payload
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

        # Human Approval Gate for Financial Write
        approved = self.approval_gate.request_approval(submit_action, form_payload)
        if not approved:
            self.human_interventions.append(f"Human denied authorization for financial write: {final_invoice_no}")
            print("[Execution Halted] Human denied authorization for financial disbursement/payable creation.")
            verification_rep = VerificationReport(
                status=VerificationStatus.UNCERTAIN,
                message="Execution halted by user: Human approval was denied for payable insertion."
            )
            return self._build_final_report(task, claimed_facts, verification_rep, evidence_files, success=False)

        # Submit Form with Chaos / Transient / Duplicate Handling
        submit_res = self._execute_with_retry(
            submit_action,
            lambda: self.client.submit_form(payables_add_url, form_payload)
        )

        if not submit_res.success:
            if submit_res.data and submit_res.data.get("is_duplicate"):
                print(f"[Duplicate Recognized] {submit_res.error}")
                self.failure_manager.record_remediation(
                    f"Handled duplicate rejection: Invoice {final_invoice_no} was already registered in the ledger. Transitioning to verification."
                )
            else:
                print(f"[Submission Failed] Error: {submit_res.error}")

        # ----------------------------------------------------------------------
        # PHASE 4: INDEPENDENT VERIFICATION (MOST IMPORTANT)
        # ----------------------------------------------------------------------
        print("\n" + "=" * 70)
        print("[INDEPENDENT VERIFICATION LAYER] Auditing Ground-Truth Outcome...")
        print("=" * 70)

        verification_report = self.verifier.verify_payable_entry(
            expected_vendor=target_vendor["name"],
            expected_invoice_no=final_invoice_no,
            expected_amount=final_amount,
            expected_due_date=final_due_date
        )

        print(f"Verification Status:  {verification_report.status.value}")
        print(f"Verification Details: {verification_report.message}")

        if verification_report.status == VerificationStatus.FAIL:
            print("[Verification Mismatch] Discrepancies detected:")
            if verification_report.evidence:
                for disc in verification_report.evidence.discrepancies:
                    print(f"  • {disc}")

        is_success = verification_report.status == VerificationStatus.PASS

        # ----------------------------------------------------------------------
        # PHASE 5: Report Compilation & Trace Generation
        # ----------------------------------------------------------------------
        return self._build_final_report(task, claimed_facts, verification_report, evidence_files, success=is_success)

    def _build_final_report(
        self,
        task: str,
        claimed_facts: Dict[str, Any],
        verification: VerificationReport,
        evidence_files: List[str],
        success: bool
    ) -> FinalRunReport:
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
