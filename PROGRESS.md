# Progress Changelog

All notable updates, milestones, and working states are logged here in reverse chronological order.

---

### [2026-10-11] - Milestone 2: Real Running Simulated Corporate Sandbox
- **What's Done**:
  - Built **Vendor Portal (Port 8001)**:
    - FastAPI app with session cookie authentication (`vendor_admin` / `vendor_pass123`).
    - Company directory with 5 realistic vendors: Acme Cloud Corp, Global Logistics Ltd, Vertex Analytics, Nexus Software Solutions, Prime Hardware & Supplies.
    - 22 invoices spanning different dates (requiring genuine date comparison rather than static ordering).
    - Authentic downloadable PDF generation using ReportLab (`%PDF` binary format with tables, line items, and remittance details).
    - Generalization test: Standard table layout for 4 vendors; custom card grid layout for `Vertex Analytics` (`layout: cards`).
  - Built **Internal Finance System (Port 8002)**:
    - FastAPI app with session cookie authentication (`finance_user` / `finance_pass123`).
    - "Add Payable" form with vendor, invoice number, amount, due date, and notes fields.
    - Full persistence to SQLite (`sandbox/data/finance.db`).
    - Business integrity constraint: Duplicate invoice check rejecting already-registered invoices with HTTP 409 Conflict.
    - Accounts Payable ledger table and detailed record view pages.
  - Implemented **Real-World Messiness / Chaos Engine** (controlled via config/env vars, default OFF):
    - Configurable slow page latency (`CHAOS_SLOW_PAGES`, `CHAOS_DELAY_SECONDS`).
    - Transient 500 errors on form submit (`CHAOS_500_ON_SUBMIT`, `CHAOS_ERROR_RATE`).
    - Session expiration forcing re-login (`CHAOS_SESSION_EXPIRY`).
    - Enforced duplicate submission prevention (`ENFORCE_DUPLICATE_CHECK`).
  - Implemented **Ground-Truth Testing Endpoints**:
    - `GET /api/debug/state` on both ports (strictly designated for test harnesses; agent is prohibited from calling these).
  - Built startup and execution tooling:
    - `scripts/seed.py`: Generates database, vendor catalog, and authentic PDFs.
    - `scripts/run_sandbox.sh`: Shell script launching both servers.
    - `scripts/run_sandbox.py`: Cross-platform Python launcher for Windows/Linux/macOS.
  - Verification & Testing:
    - Created `tests/test_sandbox.py` (unit/integration tests via FastAPI TestClient). Passed 100%.
    - Created `scripts/verify_live_sandbox.py` (spawns real servers on ports 8001/8002, performs live HTTP requests, session auth, PDF download, form submissions, duplicate 409 checks, and debug state validation). Passed 100%.
- **What's In Progress**:
  - Designing the agent architecture: tool harness (browser/DOM, file extraction), ReAct planner, memory model, and ground-truth verification layer.
- **What's Next**:
  - Milestone 3: Implement core agent planner, tool registry (browser navigation, PDF text/date extraction, form completion), and human-in-the-loop safety checkpoints.
  - Milestone 4: Implement ground-truth verification engine and evidence generation.
- **Known Issues**:
  - None.
- **Hardcoded / Mocked Elements (Honesty Record)**:
  - *Hardcoded credentials*: Default credentials in `.env.example` (`vendor_admin:vendor_pass123` and `finance_user:finance_pass123`).
  - *Synthetic business data*: Seeded vendor names, invoice figures, and dates generated via `scripts/seed.py`.
  - *Simulated chaos triggers*: Artificial delay and simulated 500 transaction timeout injection.
  - *Note*: Both web applications, HTTP network sockets, SQLite database transactions, and generated PDF binaries are **100% real and actively running**, not mocked in memory.

---

### [2026-10-11] - Milestone 1: Repo Initialization & Groundwork Setup
- **What's Done**:
  - Initialized Git repository targeting `main` branch with remote linked to `https://github.com/Rajeevreddy-2006/CentrAlign_Project.git`.
  - Configured comprehensive `.gitignore` covering Python, Node, environment variables, caches, and execution run logs while preserving sample runs.
  - Added `.env.example` template with zero committed credentials.
  - Added MIT `LICENSE`.
  - Created initial documentation framework: `README.md`, `PROGRESS.md`, `DECISIONS.md`, and `docs/`.
  - Configured milestone development rules in `.agent/rules.md` and `.agents/rules/milestone-rules.md`.
  - Pushed initial commit to `origin main`.
