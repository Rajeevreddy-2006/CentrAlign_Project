import pytest
import os
import time
import subprocess
import sys
from pathlib import Path

from agent.runner import AutonomousTaskWorker
from agent.models import VerificationStatus
from sandbox.finance_system.db import clear_payables, get_payables

REPO_ROOT = Path(__file__).resolve().parent.parent

@pytest.fixture(scope="module", autouse=True)
def start_sandbox_servers():
    """Starts live sandbox servers for the test module."""
    # Ensure seed data exists
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "seed.py")], check=True)

    uvicorn_cmd = [sys.executable, "-m", "uvicorn"]
    p_vendor = subprocess.Popen(
        uvicorn_cmd + ["sandbox.vendor_portal.app:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "warning"],
        cwd=str(REPO_ROOT)
    )
    p_finance = subprocess.Popen(
        uvicorn_cmd + ["sandbox.finance_system.app:app", "--host", "127.0.0.1", "--port", "8002", "--log-level", "warning"],
        cwd=str(REPO_ROOT)
    )

    # Wait for ports to be ready
    import requests
    ready = False
    for _ in range(25):
        try:
            r1 = requests.get("http://127.0.0.1:8001/login", timeout=1)
            r2 = requests.get("http://127.0.0.1:8002/login", timeout=1)
            if r1.status_code == 200 and r2.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.5)

    assert ready, "Sandbox servers failed to initialize on ports 8001/8002."

    yield

    p_vendor.terminate()
    p_finance.terminate()
    p_vendor.wait()
    p_finance.wait()

@pytest.fixture(autouse=True)
def reset_database():
    clear_payables()
    yield
    clear_payables()

def test_happy_path_with_independent_verification():
    """Tests standard flow: discover latest invoice, extract, enter in ERP, independent verify PASS."""
    task = "Find the latest invoice from Acme Cloud Corp, extract the amount and due date, enter it into our internal system, and tell me once it is done."
    worker = AutonomousTaskWorker(auto_approve=True, interactive=False)
    report = worker.run(task)

    assert report.success is True
    assert report.verification.status == VerificationStatus.PASS
    assert report.claimed_facts["invoice_no"] == "INV-ACME-1004"
    assert report.claimed_facts["amount"] == 2490.75
    assert report.claimed_facts["due_date"] == "2026-10-30"

    # Verify report distinguished claimed vs verified
    assert report.verification.evidence.destination_invoice_no == "INV-ACME-1004"
    assert report.verification.evidence.destination_amount == 2490.75
    assert len(report.verification.evidence.discrepancies) == 0

def test_odd_layout_generalization_vertex_analytics():
    """Tests that the worker handles the custom card layout for Vertex Analytics."""
    task = "Find the latest invoice from Vertex Analytics, extract the amount and due date, enter it into our internal system, and tell me once it is done."
    worker = AutonomousTaskWorker(auto_approve=True, interactive=False)
    report = worker.run(task)

    assert report.success is True
    assert report.verification.status == VerificationStatus.PASS
    assert report.claimed_facts["invoice_no"] == "INV-VA-204"
    assert report.claimed_facts["amount"] == 4100.00
    assert report.claimed_facts["due_date"] == "2026-10-15"

def test_chaos_recovery_and_duplicate_resilience(monkeypatch):
    """
    Tests resilience against chaos:
    1. First run enters invoice.
    2. Second run attempts to enter the same invoice again -> duplicate 409 rejection -> worker handles gracefully & verifies.
    """
    task = "Find the latest invoice from Nexus Software Solutions, extract the amount and due date, enter it into our internal system, and tell me once it is done."
    worker1 = AutonomousTaskWorker(auto_approve=True, interactive=False)
    report1 = worker1.run(task)
    assert report1.success is True

    # Run again: duplicate invoice will be triggered
    worker2 = AutonomousTaskWorker(auto_approve=True, interactive=False)
    report2 = worker2.run(task)
    assert report2.success is True
    assert any("duplicate" in r.lower() for r in report2.remediated_failures)
    assert report2.verification.status == VerificationStatus.PASS

def test_human_clarification_on_ambiguous_task():
    """Tests that the worker asks for clarification when vendor query is ambiguous."""
    task = "Find the latest invoice from a supplier, extract the amount and due date, enter it into our internal system, and tell me once it is done."

    clarification_called = False
    def mock_clarification(question, options):
        nonlocal clarification_called
        clarification_called = True
        assert options is not None and len(options) > 0
        return "Acme Cloud Corp"

    worker = AutonomousTaskWorker(
        auto_approve=True,
        interactive=False,
        clarification_handler=mock_clarification
    )
    report = worker.run(task)

    assert clarification_called is True
    assert report.success is True
    assert report.claimed_facts["vendor"] == "Acme Cloud Corp"
    assert len(report.human_interventions) > 0

def test_human_approval_rejection_safety():
    """Tests that if human denies authorization for a financial write, the worker halts safely."""
    task = "Find the latest invoice from Global Logistics Ltd, extract the amount and due date, enter it into our internal system, and tell me once it is done."

    approval_prompted = False
    def mock_approval(action, details):
        nonlocal approval_prompted
        approval_prompted = True
        return False  # HUMAN REJECTS FINANCIAL WRITE

    worker = AutonomousTaskWorker(
        auto_approve=False,
        interactive=False,
        approval_handler=mock_approval
    )
    report = worker.run(task)

    assert approval_prompted is True
    assert report.success is False  # Safe stop
    assert report.verification.status == VerificationStatus.UNCERTAIN
    assert any("denied" in hi.lower() for hi in report.human_interventions)
