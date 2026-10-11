# Progress Changelog

All notable updates, milestones, and working states are logged here in reverse chronological order.

---

### [2026-10-11] - Milestone 3: Hardened Reliability, Failure Recovery, Independent Verification & Safety
- **What's Done**:
  - **Failure Detection & Recovery Engine** ([`agent/failure_detector.py`](agent/failure_detector.py)):
    - Detects tool exceptions, timeouts, HTTP 500 errors, DOM error banners, element absence, action loops (consecutive identical actions capped at 3), and stagnant progress (state hash deduplication).
    - Automatically retries transient errors with exponential backoff ($base \times 2^{retry}$, capped at 3 attempts).
    - Self-heals mid-task session timeouts by detecting login redirects, re-authenticating with authorized environment credentials, and resuming execution.
    - Handles duplicate invoice submissions (HTTP 409) without crashing by auditing pre-existing ledger records.
  - **Independent Verification Layer** ([`agent/verifier.py`](agent/verifier.py)):
    - Completely decoupled from the agent's internal monologue and claims.
    - Runs in an isolated session, inspects destination ERP database records (`/payables`), and compares all four core fields: Vendor, Invoice Number, Amount, and Due Date.
    - Issues an authoritative **PASS**, **FAIL**, or **UNCERTAIN** determination backed by structured evidence.
    - Explicitly segregates claimed outcomes from verified ground truth in execution reports.
  - **Human-in-the-Loop (HITL) & Safety Architecture** ([`agent/human.py`](agent/human.py), [`agent/safety.py`](agent/safety.py)):
    - Risk classification: `READ_ONLY`, `REVERSIBLE_WRITE`, and `IRREVERSIBLE_FINANCIAL_WRITE`.
    - Enforces interactive human authorization for financial writes unless `--auto-approve` is passed.
    - Safely halts and prompts the user for clarification when prompts or entities are ambiguous rather than hallucinating actions.
    - Enforces a strict domain allowlist (`127.0.0.1:8001`, `localhost:8001`, `127.0.0.1:8002`, `localhost:8002`).
    - Quarantines credentials strictly to environment variables.
    - Wraps external web and PDF text in `<untrusted_web_content>` tags as a prompt-injection defense barrier.
  - **Document & PDF Processing** ([`agent/pdf_extractor.py`](agent/pdf_extractor.py)):
    - Uses `pypdf` to extract invoice numbers, due dates, issue dates, and currency amounts directly from authentic downloaded PDF statements.
  - **CLI & Demonstration Suite**:
    - Built user-facing CLI: [`agent/cli.py`](agent/cli.py) (`python -m agent.cli --task "..."`).
    - Built live chaos demonstration script: [`scripts/demonstrate_chaos_and_recovery.py`](scripts/demonstrate_chaos_and_recovery.py).
    - Automated tests: 7/7 passing in pytest suite (`tests/test_sandbox.py` and `tests/test_agent_resilience.py`).
- **What's In Progress**:
  - Final packaging, run walkthroughs, and documentation refinement.
- **What's Next**:
  - Polish evaluation submission notes and finalize repository assets.
- **Known Issues**:
  - None.
- **Hardcoded / Mocked Elements (Honesty Record)**:
  - *Hardcoded credentials*: Default credentials in `.env.example` (`vendor_admin:vendor_pass123` and `finance_user:finance_pass123`).
  - *Synthetic business data*: Seeded vendor names and invoices generated via `scripts/seed.py`.
  - *Simulated chaos triggers*: Artificial latency and simulated transient 500 error toggles.
  - *Note*: All web interactions, DOM parsing, PDF downloads and parsing, SQLite database insertions, duplicate checks, and independent verification audits are **100% genuine and actively running**.

---

### [2026-10-11] - Milestone 2: Real Running Simulated Corporate Sandbox
- **What's Done**:
  - Built **Vendor Portal (Port 8001)** with auth, 5 vendors, 22 invoices, authentic ReportLab PDF generation, and alternative card layout for Vertex Analytics.
  - Built **Internal Finance System (Port 8002)** with auth, add payable form, SQLite persistence, and duplicate 409 rejection.
  - Configured controllable real-world chaos engine (slow pages, transient 500s, session expiry).
  - Configured testing-only ground-truth debug APIs (`GET /api/debug/state`).
  - Created `scripts/seed.py`, `scripts/run_sandbox.sh`, and `scripts/run_sandbox.py`.
  - Verified with live socket test suite.

---

### [2026-10-11] - Milestone 1: Repo Initialization & Groundwork Setup
- **What's Done**:
  - Initialized Git repository targeting `main` branch with remote linked to `https://github.com/Rajeevreddy-2006/CentrAlign_Project.git`.
  - Configured comprehensive `.gitignore`, `.env.example`, MIT `LICENSE`, `README.md`, `PROGRESS.md`, `DECISIONS.md`, and docs framework.
  - Pushed initial commit to `origin main`.
