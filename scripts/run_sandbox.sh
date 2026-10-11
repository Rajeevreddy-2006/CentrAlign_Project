#!/usr/bin/env bash
# Start both CentrAlign sandbox web applications
# Port 8001: Vendor Portal
# Port 8002: Internal Finance System

set -e

# Change to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# Ensure venv python is prioritized if present
if [ -d ".venv/bin" ]; then
    PYTHON_CMD=".venv/bin/python"
    UVICORN_CMD=".venv/bin/uvicorn"
elif [ -d ".venv/Scripts" ]; then
    PYTHON_CMD=".venv/Scripts/python"
    UVICORN_CMD=".venv/Scripts/uvicorn"
else
    PYTHON_CMD="python"
    UVICORN_CMD="uvicorn"
fi

echo "=========================================================="
echo " Starting CentrAlign Autonomous AI Task Worker Sandbox"
echo "=========================================================="
echo "Vendor Portal (Port 8001):     http://localhost:8001"
echo "Internal Finance ERP (8002):   http://localhost:8002"
echo "=========================================================="

# Check if seed data exists; if not, run seed.py
if [ ! -f "sandbox/data/vendors.json" ]; then
    echo "[Init] Seed data not found. Running scripts/seed.py..."
    $PYTHON_CMD scripts/seed.py
fi

# Trap to gracefully terminate child processes on Ctrl+C or kill
cleanup() {
    echo ""
    echo "[Shutdown] Stopping sandbox web applications..."
    kill $VP_PID $FS_PID 2>/dev/null || true
    wait $VP_PID 2>/dev/null || true
    wait $FS_PID 2>/dev/null || true
    echo "[Shutdown] All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Start Vendor Portal on 8001
$UVICORN_CMD sandbox.vendor_portal.app:app --host 0.0.0.0 --port 8001 --log-level info &
VP_PID=$!
echo "[Started] Vendor Portal running with PID $VP_PID"

# Start Internal Finance System on 8002
$UVICORN_CMD sandbox.finance_system.app:app --host 0.0.0.0 --port 8002 --log-level info &
FS_PID=$!
echo "[Started] Finance System running with PID $FS_PID"

# Wait for background processes
wait $VP_PID $FS_PID
