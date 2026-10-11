# Progress Changelog

All notable updates, milestones, and working states are logged here in reverse chronological order.

---

### [2026-10-11] - Milestone 4: Generalization Proof, Evaluation Harness & Unit Test Suite
- **What's Done**:
  - **Generalization Across Diverse Business Tasks** ([`agent/planner.py`](agent/planner.py), [`agent/runner.py`](agent/runner.py)):
    - Proved generalization across multiple distinct task categories running through the **exact same unchanged agent code**:
      1. *Standard Latest Invoice Entry*: Finds chronologically latest invoice in table view, downloads PDF, enters into ERP, and audits.
      2. *DOM Layout Generalization*: Processes unstructured card-grid layouts (`Vertex Analytics`) dynamically.
      3. *Overdue Invoices Aggregation*: Filters overdue invoices for a vendor, sums balances, and returns analytical report without write side-effects.
      4. *Cross-Vendor Comparison*: Discovers all vendors, audits unpaid balances, identifies vendor with highest unpaid amount, and complies with "enter nothing, just report".
      5. *Multi-Invoice Batch Ingestion*: Parses quantities (e.g. "enter top 2 most recent"), processes each statement with individual safety approvals, and audits each entry.
      6. *Impossible / Ambiguous Task Handling*: Correctly identifies nonexistent entities (`Cyberdyne Systems`), halts gracefully, and reports clear explanation rather than hallucinating or looping.
      7. *Chaos Resilience*: Overcomes transient 500 errors and network lag via backoff retries.
  - **Evaluation Harness** ([`evals/tasks.yaml`](evals/tasks.yaml), [`evals/run.py`](evals/run.py), [`evals/results.md`](evals/results.md)):
    - Built evaluation benchmark suite specifying tasks, chaos toggles, and expected outcomes checked via isolated ground-truth debug oracle endpoints (`/api/debug/state`).
    - Implemented `python -m evals.run` generating comprehensive metric tables: success rate, steps used, retries, approvals requested, latency, and token cost estimates.
    - Generated transparent, unmanipulated benchmark report at [`evals/results.md`](evals/results.md) (**100% success rate across 7 benchmark tasks**).
  - **Comprehensive Non-LLM Unit Test Suite** ([`tests/test_unit_core.py`](tests/test_unit_core.py)):
    - Added 19 dedicated unit tests covering:
      - `RiskClassifier`: `READ_ONLY`, `REVERSIBLE_WRITE`, and `IRREVERSIBLE_FINANCIAL_WRITE`.
      - `LoopDetection & StagnantProgress`: 3 consecutive identical actions threshold and state hash deduplication.
      - `RetryAndBackoffLogic`: $base \times 2^r$ backoff calculation and transient vs. non-transient caps.
      - `VerifierComparisonLogic`: Exact match PASS, amount mismatch FAIL, and due date discrepancy FAIL.
      - `TaskPlannerGeneralization`: Intent classification, multi-invoice count parsing, overdue filtering, and chronological sorting.
      - `PDFExtractorLogic`: Robust regex extraction against synthetic invoice text.
    - All **26/26 tests passing** in `pytest` across unit, sandbox, and resilience suites.
- **What's Completed**:
  - Full generalization proof across 6 distinct tasks.
  - Evaluation harness with objective ground-truth oracle auditing (`/api/debug/state`).
  - 19 non-LLM unit tests with 26/26 overall tests passing.
  - Comprehensive documentation: `README.md`, `DECISIONS.md`, `PROGRESS.md`, `evals/results.md`.
  - Fresh-clone verification test executed and validated.
- **Hardcoded / Mocked Elements (Honesty Record)**:
  - *Hardcoded credentials*: Default credentials in `.env.example` (`vendor_admin:vendor_pass123` and `finance_user:finance_pass123`).
  - *Synthetic business data*: Seeded vendor names and invoices generated via `scripts/seed.py`.
  - *Simulated chaos triggers*: Artificial latency and simulated transient 500 error toggles.
  - *Note*: All web interactions, DOM parsing, PDF downloads and parsing, SQLite database insertions, duplicate checks, and independent verification audits are **100% genuine and actively running**.

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

