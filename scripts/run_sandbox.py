#!/usr/bin/env python3
"""
Cross-platform launcher for CentrAlign Task Worker Sandbox.
Starts both FastAPI servers:
- Vendor Portal on port 8001
- Internal Finance System on port 8002
"""

import sys
import subprocess
import time
import signal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def main():
    print("=" * 60)
    print(" Starting CentrAlign Autonomous AI Task Worker Sandbox")
    print("=" * 60)
    print("Vendor Portal (Port 8001):   http://localhost:8001")
    print("Internal Finance ERP (8002): http://localhost:8002")
    print("=" * 60)

    # Ensure seed data exists
    vendors_file = REPO_ROOT / "sandbox" / "data" / "vendors.json"
    if not vendors_file.exists():
        print("[Init] Seed data not found. Running scripts/seed.py...")
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "seed.py")], check=True)

    # Detect uvicorn executable
    uvicorn_cmd = [sys.executable, "-m", "uvicorn"]

    # Start Vendor Portal (8001)
    p_vendor = subprocess.Popen(
        uvicorn_cmd + ["sandbox.vendor_portal.app:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "info"],
        cwd=str(REPO_ROOT)
    )
    print(f"[Started] Vendor Portal process started (PID {p_vendor.pid})")

    # Start Finance System (8002)
    p_finance = subprocess.Popen(
        uvicorn_cmd + ["sandbox.finance_system.app:app", "--host", "127.0.0.1", "--port", "8002", "--log-level", "info"],
        cwd=str(REPO_ROOT)
    )
    print(f"[Started] Finance System process started (PID {p_finance.pid})")

    print("\nPress Ctrl+C to stop both servers...\n")

    def handle_exit(signum, frame):
        print("\n[Shutdown] Stopping sandbox web applications...")
        p_vendor.terminate()
        p_finance.terminate()
        p_vendor.wait()
        p_finance.wait()
        print("[Shutdown] All servers stopped cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        while True:
            time.sleep(1)
            # Check if any process exited prematurely
            if p_vendor.poll() is not None:
                print(f"[Error] Vendor Portal exited with code {p_vendor.returncode}")
                break
            if p_finance.poll() is not None:
                print(f"[Error] Finance System exited with code {p_finance.returncode}")
                break
    except KeyboardInterrupt:
        handle_exit(None, None)

if __name__ == "__main__":
    main()
