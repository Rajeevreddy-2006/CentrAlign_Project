import os
from pathlib import Path
from typing import Set
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

# Domain allowlist for safety
ALLOWED_HOSTS: Set[str] = {
    "localhost:8001",
    "127.0.0.1:8001",
    "localhost:8002",
    "127.0.0.1:8002",
}

# Base URLs
VENDOR_PORTAL_BASE = os.getenv("VENDOR_PORTAL_BASE", "http://127.0.0.1:8001")
FINANCE_SYSTEM_BASE = os.getenv("FINANCE_SYSTEM_BASE", "http://127.0.0.1:8002")

# Credentials sourced STRICTLY from environment
VENDOR_USER = os.getenv("VENDOR_PORTAL_USER", "vendor_admin")
VENDOR_PASS = os.getenv("VENDOR_PORTAL_PASS", "vendor_pass123")

FINANCE_USER = os.getenv("FINANCE_USER", "finance_user")
FINANCE_PASS = os.getenv("FINANCE_PASS", "finance_pass123")

# LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

# Execution Limits
MAX_STEPS = int(os.getenv("MAX_STEPS", "25"))
MAX_RETRIES_PER_STEP = int(os.getenv("MAX_RETRIES_PER_STEP", "3"))
EXPONENTIAL_BACKOFF_BASE = float(os.getenv("EXPONENTIAL_BACKOFF_BASE", "1.0"))
MAX_LOOP_COUNT = int(os.getenv("MAX_LOOP_COUNT", "3"))

# Artifacts & Run Directories
RUNS_DIR = REPO_ROOT / os.getenv("RUNS_DIR", "runs")
RUNS_DIR.mkdir(parents=True, exist_ok=True)
