import pytest
from datetime import datetime
from agent.models import (
    Action,
    ActionResult,
    ActionType,
    RiskLevel,
    VerificationStatus,
    VerificationReport,
    VerificationEvidence
)
from agent.failure_detector import FailureManager, LoopDetectedError
from agent.human import classify_action_risk, HumanApprovalGate
from agent.planner import TaskPlanner
from agent.verifier import IndependentVerifier
from agent.pdf_extractor import PDFInvoiceExtractor

# ==============================================================================
# 1. RISK CLASSIFIER TESTS
# ==============================================================================
class TestRiskClassifier:
    def test_read_only_actions(self):
        nav_action = Action(
            action_type=ActionType.NAVIGATE,
            thought="Navigate to portal",
            params={"url": "http://localhost:8001/vendors"},
            risk_level=RiskLevel.READ_ONLY
        )
        assert classify_action_risk(nav_action) == RiskLevel.READ_ONLY

        login_action = Action(
            action_type=ActionType.LOGIN,
            thought="Authenticate to system",
            params={"service": "vendor"},
            risk_level=RiskLevel.READ_ONLY
        )
        assert classify_action_risk(login_action) == RiskLevel.READ_ONLY

    def test_financial_write_classification(self):
        submit_payable = Action(
            action_type=ActionType.SUBMIT_FORM,
            thought="Submit payable to finance system",
            params={"url": "http://localhost:8002/payables/add", "form_data": {"amount": "100"}},
            risk_level=RiskLevel.IRREVERSIBLE_FINANCIAL_WRITE
        )
        assert classify_action_risk(submit_payable) == RiskLevel.IRREVERSIBLE_FINANCIAL_WRITE

    def test_non_financial_write_classification(self):
        submit_filter = Action(
            action_type=ActionType.SUBMIT_FORM,
            thought="Filter search query",
            params={"url": "http://localhost:8001/search", "form_data": {"q": "acme"}},
            risk_level=RiskLevel.REVERSIBLE_WRITE
        )
        assert classify_action_risk(submit_filter) == RiskLevel.REVERSIBLE_WRITE


# ==============================================================================
# 2. LOOP DETECTION & STAGNANT PROGRESS TESTS
# ==============================================================================
class TestLoopDetectionAndFailureManager:
    def test_loop_detected_after_three_identical_actions(self):
        fm = FailureManager()
        action = Action(
            action_type=ActionType.NAVIGATE,
            thought="Attempt navigation",
            params={"url": "http://localhost:8001/vendors/acme-cloud"}
        )

        # 1st attempt: no loop
        fm.record_action(action)
        assert not fm.is_loop_detected(action)

        # 2nd attempt: no loop
        fm.record_action(action)
        assert not fm.is_loop_detected(action)

        # 3rd attempt: loop detected!
        fm.record_action(action)
        assert fm.is_loop_detected(action)

    def test_loop_not_triggered_for_different_actions(self):
        fm = FailureManager()
        a1 = Action(action_type=ActionType.NAVIGATE, thought="a1", params={"url": "http://localhost:8001/1"})
        a2 = Action(action_type=ActionType.NAVIGATE, thought="a2", params={"url": "http://localhost:8001/2"})
        a3 = Action(action_type=ActionType.NAVIGATE, thought="a3", params={"url": "http://localhost:8001/1"})

        fm.record_action(a1)
        fm.record_action(a2)
        fm.record_action(a3)
        assert not fm.is_loop_detected(a3)

    def test_stagnant_progress_detection(self):
        fm = FailureManager()
        action = Action(
            action_type=ActionType.SUBMIT_FORM,
            thought="Submit form",
            params={"url": "http://localhost:8002/payables/add"}
        )
        res1 = ActionResult(action_type=ActionType.SUBMIT_FORM, success=False, state_hash="hash_abc123")
        res2 = ActionResult(action_type=ActionType.SUBMIT_FORM, success=False, state_hash="hash_abc123")

        # First failure records hash
        assert not fm.check_stagnant_progress(action, res1)
        # Second failure with exact same hash signals stagnant progress
        assert fm.check_stagnant_progress(action, res2)


# ==============================================================================
# 3. RETRY & EXPONENTIAL BACKOFF LOGIC TESTS
# ==============================================================================
class TestRetryAndBackoffLogic:
    def test_exponential_backoff_calculation(self):
        fm = FailureManager()
        # BASE = 1.0; formula: base * (2 ** retry_count)
        # retry_count = 1 -> 2.0s
        # retry_count = 2 -> 4.0s
        # retry_count = 3 -> 8.0s
        assert fm.compute_backoff(1) == 2.0
        assert fm.compute_backoff(2) == 4.0
        assert fm.compute_backoff(3) == 8.0

    def test_should_retry_transient_within_cap(self):
        fm = FailureManager()
        transient_res = ActionResult(
            action_type=ActionType.SUBMIT_FORM,
            success=False,
            is_transient=True,
            error="HTTP 500 Transient Error"
        )
        fatal_res = ActionResult(
            action_type=ActionType.SUBMIT_FORM,
            success=False,
            is_transient=False,
            error="HTTP 404 Not Found"
        )

        assert fm.should_retry_transient(transient_res, retry_count=0) is True
        assert fm.should_retry_transient(transient_res, retry_count=1) is True
        assert fm.should_retry_transient(transient_res, retry_count=2) is True
        # Max retry cap reached (default 3)
        assert fm.should_retry_transient(transient_res, retry_count=3) is False

        # Non-transient should never retry
        assert fm.should_retry_transient(fatal_res, retry_count=0) is False

    def test_session_expiry_detection(self):
        fm = FailureManager()
        res_expired = ActionResult(
            action_type=ActionType.NAVIGATE,
            success=False,
            current_url="http://localhost:8001/login?error=Session+expired",
            data={"is_session_expired": True}
        )
        assert fm.is_session_expired(res_expired) is True

        res_ok = ActionResult(
            action_type=ActionType.NAVIGATE,
            success=True,
            current_url="http://localhost:8001/vendors"
        )
        assert fm.is_session_expired(res_ok) is False


# ==============================================================================
# 4. VERIFIER'S COMPARISON LOGIC TESTS
# ==============================================================================
class TestVerifierComparisonLogic:
    def test_comparison_exact_match(self):
        evidence = VerificationEvidence(
            source_vendor="Acme Cloud Corp",
            source_invoice_no="INV-ACME-1004",
            source_amount=2490.75,
            source_due_date="2026-10-30",
            destination_vendor="Acme Cloud Corp",
            destination_invoice_no="INV-ACME-1004",
            destination_amount=2490.75,
            destination_due_date="2026-10-30"
        )
        discrepancies = []
        if evidence.source_invoice_no.lower() != evidence.destination_invoice_no.lower():
            discrepancies.append("Invoice mismatch")
        if abs(evidence.source_amount - evidence.destination_amount) > 0.01:
            discrepancies.append("Amount mismatch")
        if evidence.source_due_date.strip() != evidence.destination_due_date.strip():
            discrepancies.append("Due date mismatch")

        assert len(discrepancies) == 0

    def test_comparison_detects_amount_discrepancy(self):
        evidence = VerificationEvidence(
            source_vendor="Acme Cloud Corp",
            source_invoice_no="INV-ACME-1004",
            source_amount=2490.75,
            source_due_date="2026-10-30",
            destination_vendor="Acme Cloud Corp",
            destination_invoice_no="INV-ACME-1004",
            destination_amount=1999.00,  # Intentional discrepancy
            destination_due_date="2026-10-30"
        )
        discrepancies = []
        if abs(evidence.source_amount - evidence.destination_amount) > 0.01:
            discrepancies.append(f"Amount mismatch: {evidence.source_amount} vs {evidence.destination_amount}")

        assert len(discrepancies) == 1
        assert "Amount mismatch" in discrepancies[0]

    def test_comparison_detects_due_date_discrepancy(self):
        evidence = VerificationEvidence(
            source_vendor="Acme Cloud Corp",
            source_invoice_no="INV-ACME-1004",
            source_amount=2490.75,
            source_due_date="2026-10-30",
            destination_vendor="Acme Cloud Corp",
            destination_invoice_no="INV-ACME-1004",
            destination_amount=2490.75,
            destination_due_date="2026-11-15"  # Mismatch
        )
        discrepancies = []
        if evidence.source_due_date.strip() != evidence.destination_due_date.strip():
            discrepancies.append("Due date mismatch")

        assert len(discrepancies) == 1


# ==============================================================================
# 5. TASK PLANNER INTENT & GENERALIZATION TESTS
# ==============================================================================
class TestTaskPlannerGeneralization:
    def test_classify_standard_entry(self):
        plan = TaskPlanner.classify_task_intent(
            "Find the latest invoice from Acme Cloud Corp, extract amount and due date, and enter into internal system."
        )
        assert plan["intent"] == "ENTER_INVOICES"
        assert plan["vendor_query"] == "Acme Cloud Corp"
        assert plan["count"] == 1
        assert plan["requires_entry"] is True

    def test_classify_multi_invoice_entry(self):
        plan = TaskPlanner.classify_task_intent(
            "Enter the 2 most recent invoices from Acme Cloud Corp into the finance system."
        )
        assert plan["intent"] == "ENTER_INVOICES"
        assert plan["vendor_query"] == "Acme Cloud Corp"
        assert plan["count"] == 2
        assert plan["requires_entry"] is True

    def test_classify_overdue_reporting(self):
        plan = TaskPlanner.classify_task_intent(
            "List all invoices from Acme Cloud Corp that are overdue and tell me the total."
        )
        assert plan["intent"] == "REPORT_OVERDUE"
        assert plan["vendor_query"] == "Acme Cloud Corp"
        assert plan["requires_entry"] is False

    def test_classify_highest_unpaid_vendor(self):
        plan = TaskPlanner.classify_task_intent(
            "Which vendor has the highest unpaid amount? Enter nothing, just report."
        )
        assert plan["intent"] == "REPORT_HIGHEST_UNPAID"
        assert plan["requires_entry"] is False

    def test_filter_overdue_invoices(self):
        sample_invoices = [
            {"invoice_no": "INV-1", "due_date": "2026-05-01", "status": "Paid", "amount": 100},
            {"invoice_no": "INV-2", "due_date": "2026-08-01", "status": "Overdue", "amount": 200},
            {"invoice_no": "INV-3", "due_date": "2026-09-01", "status": "Open", "amount": 300}, # Prior to ref date 2026-10-11
            {"invoice_no": "INV-4", "due_date": "2026-11-01", "status": "Open", "amount": 400}, # Future
        ]
        overdue = TaskPlanner.filter_overdue_invoices(sample_invoices, reference_date="2026-10-11")
        overdue_nos = [i["invoice_no"] for i in overdue]
        assert "INV-2" in overdue_nos
        assert "INV-3" in overdue_nos
        assert "INV-1" not in overdue_nos
        assert "INV-4" not in overdue_nos

    def test_select_latest_invoice_compares_dates_strictly(self):
        invoices = [
            {"invoice_no": "INV-EARLY", "issue_date": "2025-01-01"},
            {"invoice_no": "INV-LATEST", "issue_date": "2026-10-01"},
            {"invoice_no": "INV-MID", "issue_date": "2026-06-15"}
        ]
        latest = TaskPlanner.select_latest_invoice(invoices)
        assert latest["invoice_no"] == "INV-LATEST"


# ==============================================================================
# 6. PDF EXTRACTOR PARSING LOGIC TESTS
# ==============================================================================
class TestPDFExtractorLogic:
    def test_regex_extraction_from_simulated_text(self):
        sample_text = """
        INVOICE STATEMENT
        Invoice Number: INV-ACME-9999
        Issue Date: 2026-09-15
        Due Date: 2026-10-15
        Vendor: Acme Cloud Corp
        Balance Due: $3,450.50 USD
        """
        extracted = PDFInvoiceExtractor.extract_from_text(sample_text)
        assert extracted["invoice_no"] == "INV-ACME-9999"
        assert extracted["due_date"] == "2026-10-15"
        assert extracted["amount"] == 3450.50
