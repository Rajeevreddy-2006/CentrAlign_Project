import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Base Sandbox Directories
SANDBOX_DIR = BASE_DIR / "sandbox"
DATA_DIR = SANDBOX_DIR / "data"
INVOICES_DIR = DATA_DIR / "invoices"
VENDORS_FILE = DATA_DIR / "vendors.json"
FINANCE_DB_PATH = DATA_DIR / "finance.db"

# Server Ports
VENDOR_PORTAL_PORT = int(os.getenv("VENDOR_PORTAL_PORT", "8001"))
FINANCE_SYSTEM_PORT = int(os.getenv("FINANCE_SYSTEM_PORT", "8002"))

# Fake Credentials
VENDOR_USER = os.getenv("VENDOR_PORTAL_USER", "vendor_admin")
VENDOR_PASS = os.getenv("VENDOR_PORTAL_PASS", "vendor_pass123")

FINANCE_USER = os.getenv("FINANCE_USER", "finance_user")
FINANCE_PASS = os.getenv("FINANCE_PASS", "finance_pass123")

# Secret Key for Cookie Sessions
SECRET_KEY = os.getenv("SANDBOX_SECRET_KEY", "centralign-task-worker-sandbox-secret-2026")

# Real-World Messiness / Chaos Controls (Default: OFF)
CHAOS_MODE = os.getenv("CHAOS_MODE", "false").lower() in ("true", "1", "yes")
CHAOS_SLOW_PAGES = os.getenv("CHAOS_SLOW_PAGES", "false").lower() in ("true", "1", "yes") or CHAOS_MODE
CHAOS_DELAY_SECONDS = float(os.getenv("CHAOS_DELAY_SECONDS", "1.5"))

CHAOS_500_ON_SUBMIT = os.getenv("CHAOS_500_ON_SUBMIT", "false").lower() in ("true", "1", "yes") or CHAOS_MODE
CHAOS_ERROR_RATE = float(os.getenv("CHAOS_ERROR_RATE", "0.35"))

CHAOS_SESSION_EXPIRY = os.getenv("CHAOS_SESSION_EXPIRY", "false").lower() in ("true", "1", "yes") or CHAOS_MODE
CHAOS_SESSION_MAX_REQUESTS = int(os.getenv("CHAOS_SESSION_MAX_REQUESTS", "3"))

# Business Integrity Rule (Always active by default to test worker handling)
ENFORCE_DUPLICATE_CHECK = os.getenv("ENFORCE_DUPLICATE_CHECK", "true").lower() in ("true", "1", "yes")
