import pytest
from fastapi.testclient import TestClient

from sandbox.vendor_portal.app import app as vendor_app
from sandbox.finance_system.app import app as finance_app
from sandbox.finance_system.db import clear_payables, get_payables

@pytest.fixture(autouse=True)
def clean_db():
    clear_payables()
    yield
    clear_payables()

def test_vendor_portal_auth_and_navigation():
    client = TestClient(vendor_app)

    # 1. Unauthenticated redirect to /login
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
    assert "/login" in resp.headers["location"]

    # 2. Failed login
    resp = client.post("/login", data={"username": "wrong", "password": "bad"}, follow_redirects=False)
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.text

    # 3. Successful login
    resp = client.post("/login", data={"username": "vendor_admin", "password": "vendor_pass123"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/vendors"
    assert "vp_session" in resp.cookies

    # 4. Access /vendors with session cookie
    resp = client.get("/vendors")
    assert resp.status_code == 200
    assert "Acme Cloud Corp" in resp.text
    assert "Vertex Analytics" in resp.text
    assert "Global Logistics Ltd" in resp.text

    # 5. Access standard table layout for Acme Cloud
    resp = client.get("/vendors/acme-cloud")
    assert resp.status_code == 200
    assert "invoices-table" in resp.text
    assert "INV-ACME-1004" in resp.text
    assert "Download PDF" in resp.text

    # 6. Access alternative card layout for Vertex Analytics
    resp = client.get("/vendors/vertex-analytics")
    assert resp.status_code == 200
    assert "invoices-grid" in resp.text
    assert "invoice-card" in resp.text
    assert "INV-VA-204" in resp.text

    # 7. Test PDF download returns valid PDF binary
    resp = client.get("/download/acme-cloud/INV-ACME-1004.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")

    # 8. Test Ground Truth Debug API
    resp = client.get("/api/debug/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "_warning" in data
    assert data["vendors_count"] == 5
    assert "ground_truth_latest_invoices" in data
    assert data["ground_truth_latest_invoices"]["Acme Cloud Corp"]["invoice_no"] == "INV-ACME-1004"
    assert data["ground_truth_latest_invoices"]["Global Logistics Ltd"]["invoice_no"] == "INV-GL-505"
    assert data["ground_truth_latest_invoices"]["Vertex Analytics"]["invoice_no"] == "INV-VA-204"

def test_finance_system_auth_and_payables_lifecycle():
    client = TestClient(finance_app)

    # 1. Unauthenticated redirect to /login
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
    assert "/login" in resp.headers["location"]

    # 2. Successful login
    resp = client.post("/login", data={"username": "finance_user", "password": "finance_pass123"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/payables"
    assert "finance_session" in resp.cookies

    # 3. View empty ledger
    resp = client.get("/payables")
    assert resp.status_code == 200
    assert "No Accounts Payable Logged Yet" in resp.text

    # 4. Add Payable entry
    payload = {
        "vendor": "Acme Cloud Corp",
        "invoice_no": "INV-ACME-1004",
        "amount": 2490.75,
        "due_date": "2026-10-30",
        "notes": "Verified latest invoice for Q3 Cloud Capacity."
    }
    resp = client.post("/payables/add", data=payload, follow_redirects=False)
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert "/payables/" in location

    # 5. Check Detail Page
    resp = client.get(location)
    assert resp.status_code == 200
    assert "Acme Cloud Corp" in resp.text
    assert "INV-ACME-1004" in resp.text
    assert "2,490.75" in resp.text
    assert "2026-10-30" in resp.text

    # 6. Check Ledger Table now has the row
    resp = client.get("/payables")
    assert resp.status_code == 200
    assert "payables-table" in resp.text
    assert "INV-ACME-1004" in resp.text

    # 7. Duplicate Check: Attempt to enter the same invoice again
    resp = client.post("/payables/add", data=payload, follow_redirects=False)
    assert resp.status_code == 409
    assert "Duplicate invoice rejected" in resp.text

    # 8. Test Ground Truth Debug API
    resp = client.get("/api/debug/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "_warning" in data
    assert data["payables_count"] == 1
    assert data["payables"][0]["invoice_no"] == "INV-ACME-1004"
