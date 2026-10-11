#!/usr/bin/env python3
"""
Live end-to-end socket verification test.
Starts real Uvicorn servers on ports 8001 and 8002, performs live HTTP requests,
and asserts full functionality across both apps.
"""

import sys
import time
import subprocess
from pathlib import Path
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent

def main():
    print("[Live Test] Starting live sandbox servers...")
    uvicorn_cmd = [sys.executable, "-m", "uvicorn"]

    # 1. Start Vendor Portal (8001)
    p_vendor = subprocess.Popen(
        uvicorn_cmd + ["sandbox.vendor_portal.app:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "warning"],
        cwd=str(REPO_ROOT)
    )

    # 2. Start Finance System (8002)
    p_finance = subprocess.Popen(
        uvicorn_cmd + ["sandbox.finance_system.app:app", "--host", "127.0.0.1", "--port", "8002", "--log-level", "warning"],
        cwd=str(REPO_ROOT)
    )

    try:
        # Wait for servers to be up
        print("[Live Test] Polling ports 8001 and 8002...")
        vp_ready = False
        fs_ready = False
        for _ in range(30):
            try:
                if not vp_ready:
                    r = requests.get("http://127.0.0.1:8001/login", timeout=1)
                    if r.status_code == 200:
                        vp_ready = True
                if not fs_ready:
                    r = requests.get("http://127.0.0.1:8002/login", timeout=1)
                    if r.status_code == 200:
                        fs_ready = True
                if vp_ready and fs_ready:
                    break
            except Exception:
                time.sleep(0.5)

        if not (vp_ready and fs_ready):
            print("[Live Test] ERROR: Servers failed to start within timeout.")
            sys.exit(1)

        print("[Live Test] Both servers responded on live ports!")

        # Test Vendor Portal with requests.Session
        print("[Live Test] Testing Vendor Portal (Port 8001)...")
        vp_session = requests.Session()
        r = vp_session.post("http://127.0.0.1:8001/login", data={"username": "vendor_admin", "password": "vendor_pass123"}, allow_redirects=True)
        assert r.status_code == 200, f"Login failed with status {r.status_code}"
        assert "Vendor Directory" in r.text
        print("  -> Login successful (Session cookie received)")

        r = vp_session.get("http://127.0.0.1:8001/vendors/acme-cloud")
        assert r.status_code == 200
        assert "INV-ACME-1004" in r.text
        print("  -> Vendor invoices table rendered (Acme Cloud)")

        r = vp_session.get("http://127.0.0.1:8001/vendors/vertex-analytics")
        assert r.status_code == 200
        assert "invoices-grid" in r.text
        assert "INV-VA-204" in r.text
        print("  -> Custom card grid layout rendered (Vertex Analytics)")

        r = vp_session.get("http://127.0.0.1:8001/download/acme-cloud/INV-ACME-1004.pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content.startswith(b"%PDF")
        print(f"  -> PDF download successful ({len(r.content)} bytes, valid %PDF header)")

        r = vp_session.get("http://127.0.0.1:8001/api/debug/state")
        assert r.status_code == 200
        dbg = r.json()
        assert dbg["vendors_count"] == 5
        print(f"  -> Debug state ground truth verified ({dbg['invoices_total']} invoices across 5 vendors)")

        # Test Finance System with requests.Session
        print("[Live Test] Testing Internal Finance ERP (Port 8002)...")
        fs_session = requests.Session()
        r = fs_session.post("http://127.0.0.1:8002/login", data={"username": "finance_user", "password": "finance_pass123"}, allow_redirects=True)
        assert r.status_code == 200
        assert "Accounts Payable Ledger" in r.text
        print("  -> Login successful (Finance session active)")

        # Submit new payable
        payable_data = {
            "vendor": "Acme Cloud Corp",
            "invoice_no": "INV-ACME-1004",
            "amount": "2490.75",
            "due_date": "2026-10-30",
            "notes": "Verified latest invoice submitted via live test harness."
        }
        r = fs_session.post("http://127.0.0.1:8002/payables/add", data=payable_data, allow_redirects=True)
        assert r.status_code == 200
        assert "Payable Record #" in r.text
        assert "2,490.75" in r.text
        print("  -> Payable submitted & detail page loaded")

        # Test duplicate rejection
        r = fs_session.post("http://127.0.0.1:8002/payables/add", data=payable_data, allow_redirects=False)
        assert r.status_code == 409
        assert "Duplicate invoice rejected" in r.text
        print("  -> Duplicate check successfully rejected duplicate invoice (HTTP 409)")

        # Test Finance Debug State
        r = fs_session.get("http://127.0.0.1:8002/api/debug/state")
        assert r.status_code == 200
        fs_dbg = r.json()
        assert fs_dbg["payables_count"] >= 1
        print(f"  -> SQLite ground truth verified ({fs_dbg['payables_count']} payable entries in DB)")

        print("\n[SUCCESS] Both sandbox web applications passed all live socket tests!")

    finally:
        print("[Live Test] Cleaning up server processes...")
        p_vendor.terminate()
        p_finance.terminate()
        p_vendor.wait()
        p_finance.wait()
        print("[Live Test] Cleanup complete.")

if __name__ == "__main__":
    main()
