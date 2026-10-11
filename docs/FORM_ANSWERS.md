# CentrAlign AI Internship — Submission & Technical Interview Defense Guide

This document contains plain, first-person answers to the Google Form submission questions, strictly grounded in the active codebase and benchmark results. It is accompanied by a technical interview cheat sheet with direct code and function references.

---

## Part 1: Official Submission Form Answers

### 1. In 3–5 sentences, what did I build?
I built an autonomous AI task worker that executes multi-step computer tasks across corporate web portals and internal systems from natural language instructions. The worker inspects vendor directories, parses diverse layout structures (tables and card grids), downloads and validates authentic binary invoice PDFs, and logs records into an internal finance ERP. It incorporates an automated recovery engine that overcomes network latency, transient 500 errors via exponential backoff, and mid-task session expirations. Most importantly, it enforces a human approval gate for financial writes and subject all outcomes to an independent verification layer that audits destination SQLite records directly rather than trusting the agent's claims.

---

### 2. Briefly explain my architecture.
My architecture uses a modular execution pipeline:
1. **Task Planner (`agent/planner.py`)**: Decomposes natural language instructions into operational intents (`ENTER_INVOICES`, `REPORT_OVERDUE`, `REPORT_HIGHEST_UNPAID`, `REPORT_GENERAL`), resolves entities, and sorts invoice dates strictly chronologically.
2. **Browser Client (`agent/browser_client.py`)**: Session-aware HTTP client with BeautifulSoup that navigates portals, tracks cookies, parses HTML, and generates state hashes.
3. **Failure Recovery Engine (`agent/failure_detector.py`)**: Detects loops (3-strike action limit), stagnant DOM states, and transient HTTP errors, calculating exponential backoff and initiating auto-relogin.
4. **Safety & Risk Gate (`agent/human.py`, `agent/safety.py`)**: Classifies actions into risk tiers (`READ_ONLY`, `REVERSIBLE_WRITE`, `IRREVERSIBLE_FINANCIAL_WRITE`), enforcing human approval before ERP submissions.
5. **Independent Verifier (`agent/verifier.py`)**: An isolated audit layer that inspects the destination SQLite ERP ledger across four key dimensions (Vendor, Invoice #, Amount, Due Date).

---

### 3. What parts of my system are genuinely autonomous?
- **Chronological Date Comparison**: Invoices are never assumed to be ordered in the DOM; issue dates are parsed and compared across all rows/cards to determine the true latest invoice.
- **Heterogeneous DOM Adaptation**: The worker extracts data across both traditional HTML tables and CSS card grids without hardcoded selector assumptions.
- **Mid-Task Re-Authentication**: When a portal session expires mid-workflow, the worker autonomously detects the `/login` redirect, re-authenticates using environment credentials, and resumes execution without human intervention.
- **Transient Error Remediation**: On receiving transient HTTP 500 errors, the worker calculates exponential backoff and retries.
- **Ambiguity Escalation & Nonexistent Entity Refusal**: When given a nonexistent vendor (e.g., `Cyberdyne Systems`), it identifies zero matches and cleanly refuses rather than hallucinating actions.
- **Independent Verification**: Evaluates ground truth directly against the SQLite database.

---

### 4. What is currently hardcoded or manually configured?
- **Domain Allowlist**: The network client is explicitly restricted to `localhost:8001` and `localhost:8002` in `agent/config.py` for safety.
- **Credentials**: Stored in `.env` and injected via environment variables (`vendor_admin:vendor_pass123`, `finance_user:finance_pass123`).
- **Synthetic Business Data**: Generated via ReportLab in `scripts/seed.py` (5 vendors, 22 invoices).
- **Rule-Based Intent Classifier**: Decomposes prompts via regex and semantic intent rules rather than live LLM API calls in the local benchmark mode.
- **Token Estimation**: Uses a deterministic proxy of 450 tokens per step for consistent benchmark cost modeling in `evals/run.py`.

---

### 5. What models, frameworks, APIs, libraries, AI coding tools, or existing projects did I use?
- **AI Coding Tool**: Built and iterated using **Google Antigravity IDE** (DeepMind Agentic AI Pair Programming platform) with Gemini 2.5 architecture context.
- **Sandbox Backend**: `FastAPI` (v0.110+), `Uvicorn`, `Jinja2` templates, and `SQLite3`.
- **Document & Web Parsing**: `reportlab` (synthetic PDF creation), `pypdf` (binary statement parsing), `BeautifulSoup4` (DOM traversal), and `requests` (cookie session management).
- **Testing & Benchmarking**: `pytest`, `pytest-asyncio`, `httpx`, and `PyYAML`.
- **Pre-built Templates**: Simple vanilla HTML/CSS templates for the sandbox portals; all core agent logic, failure managers, verifiers, and test suites were written from scratch.

---

### 6. What is the biggest technical limitation of my current solution?
The biggest limitation is that the `BrowserClient` relies on HTTP requests and BeautifulSoup DOM parsing rather than a headless browser engine like Playwright. While this makes it exceptionally fast, lightweight, and deterministic for server-rendered HTML, it cannot execute client-side JavaScript, single-page application (SPA) virtual DOM rendering, or canvas-based interactive elements. Furthermore, PDF text extraction uses textual regex parsing; scanned raster bitmap invoices would require an integrated OCR model.

---

### 7. If I had another 2 weeks, what would I build or change next?
1. **Dual-Engine Browser Driver**: Integrate Playwright alongside the lightweight HTTP client, automatically switching to a full headless Chromium browser when JavaScript hydration is detected.
2. **Multimodal Visual Verification**: Capture full-page DOM screenshots on failure or verification and query Gemini 2.5 Flash Vision to detect visual discrepancies and layout anomalies.
3. **Compensating Rollback Transactions**: Implement transactional undo actions (e.g., voiding or deleting a payable entry) if an end-to-end task fails downstream after a write.
4. **Persistent Selector & Schema Memory**: Maintain an episodic memory store of vendor invoice schemas, past layout changes, and selector patterns across runs to speed up future runs.

---

## Part 2: Technical Interview Cheat Sheet (10 Tough Questions & Proofs)

### Q1: "Why did you build your browser client with requests and BeautifulSoup instead of Playwright or Selenium?"
- **Answer**: I evaluated Playwright, but choosing a session-backed HTTP client with BeautifulSoup gave me deterministic speed (<0.3s per step), zero browser-driver binary crashes, and zero rendering flakiness during automated evaluations. For standard enterprise portals with server-rendered forms, session cookies, and tables, an HTTP client with state-hash tracking and DOM parsing is far more reliable and easier to test in CI/CD.
- **Code Pointer**: [`agent/browser_client.py:BrowserClient`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/browser_client.py#L10-L45), [`DECISIONS.md:DEC-0003`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/DECISIONS.md).

---

### Q2: "How do you ensure the agent doesn't just hallucinate that it entered the invoice correctly?"
- **Answer**: I completely decoupled outcome verification from the agent's execution loop. The agent does not verify itself. When the agent calls finish, an isolated `IndependentVerifier` class spawns, authenticates separately, navigates to `/payables`, and queries the SQLite database directly. It extracts the destination vendor, invoice number, amount, and due date, comparing them mathematically and textually against the source facts. If any field differs or the record is missing, it returns a hard `FAIL`.
- **Code Pointer**: [`agent/verifier.py:IndependentVerifier.verify_payable_entry()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/verifier.py#L17-L142), [`tests/test_unit_core.py:TestVerifierComparisonLogic`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/tests/test_unit_core.py#L125-L175).

---

### Q3: "How does your agent determine the 'latest' invoice? What if the table isn't sorted chronologically?"
- **Answer**: The agent never assumes the first row or top card is the latest. `TaskPlanner.sort_invoices_by_date()` and `select_latest_invoice()` parse the `issue_date` string from every extracted invoice into a `datetime` object (`%Y-%m-%d`) and performs a strict descending sort. In our test data for Acme Cloud, `INV-ACME-1004` (issued 2026-09-30) is correctly selected over older invoices regardless of display position.
- **Code Pointer**: [`agent/planner.py:TaskPlanner.sort_invoices_by_date()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/planner.py#L119-L135).

---

### Q4: "What happens when the simulated corporate app throws a 500 Internal Server Error?"
- **Answer**: In `BrowserClient.submit_form()`, HTTP status codes $\ge 500$ are flagged with `is_transient = True`. `FailureManager.should_retry_transient()` checks whether the attempt is within the retry limit (`MAX_RETRIES_PER_STEP = 3`). If so, `FailureManager.compute_backoff()` calculates exponential backoff ($1.0 \times 2^{retry}$ seconds), sleeps, logs the remediation note, and retries the submission.
- **Code Pointer**: [`agent/failure_detector.py:FailureManager.should_retry_transient()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/failure_detector.py#L67-L79), [`agent/runner.py:_execute_with_retry()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/runner.py#L76-L115).

---

### Q5: "How does the agent handle mid-task session expiration?"
- **Answer**: Both simulated portals have a chaos setting that expires sessions after $N$ requests. When a request returns a redirect to `/login` with an error banner, `FailureManager.is_session_expired()` detects it. Instead of crashing, `_execute_with_retry()` identifies which portal expired (8001 vs 8002), calls `BrowserClient.login()` using environment credentials, logs the recovery remediation, and immediately replays the interrupted action.
- **Code Pointer**: [`agent/runner.py:AutonomousTaskWorker._execute_with_retry()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/runner.py#L88-L103), [`agent/failure_detector.py:is_session_expired()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/failure_detector.py#L54-L65).

---

### Q6: "How do you prevent the agent from getting stuck in an infinite loop?"
- **Answer**: I implemented a 3-strike loop detector in `FailureManager`. Every action records an immutable tuple signature: `(action_type, json.dumps(params, sort_keys=True))`. Before executing any step, `is_loop_detected()` inspects the last 3 entries in `action_history`. If all 3 are identical, it raises `LoopDetectedError` and halts execution rather than burning tokens or thrashing the system.
- **Code Pointer**: [`agent/failure_detector.py:FailureManager.is_loop_detected()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/failure_detector.py#L30-L40), [`tests/test_unit_core.py:test_loop_detected_after_three_identical_actions`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/tests/test_unit_core.py#L46-L65).

---

### Q7: "How do you protect against dangerous or irreversible actions like financial disbursements?"
- **Answer**: I implemented a risk classification hierarchy in `agent/human.py`. Every action is inspected by `classify_action_risk()`:
  - Navigation, page reading, and PDF downloads $\rightarrow$ `READ_ONLY`
  - Search queries $\rightarrow$ `REVERSIBLE_WRITE`
  - Submitting forms to `/payables/add` $\rightarrow$ `IRREVERSIBLE_FINANCIAL_WRITE`
  Any financial write triggers `HumanApprovalGate.request_approval()`, displaying the vendor, invoice #, amount, and due date, requiring an explicit terminal confirmation (`yes/no`). If rejected, execution safely aborts.
- **Code Pointer**: [`agent/human.py:classify_action_risk()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/human.py#L5-L17), [`agent/runner.py:AutonomousTaskWorker.run()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/runner.py#L380-L395).

---

### Q8: "How does your code prove generalization across different tasks and layouts without hardcoded hacks?"
- **Answer**: The agent runs the **exact same codebase** across 7 diverse tasks in `evals/tasks.yaml`:
  1. *Tables* (Acme, Global Logistics) vs. *Cards Grid* (Vertex Analytics): `BrowserClient.extract_invoices_from_page()` parses both structures dynamically.
  2. *Analytical Reports*: `REPORT_OVERDUE` aggregates unpaid balances without triggering write workflows.
  3. *Comparative Discovery*: `REPORT_HIGHEST_UNPAID` inspects all vendors, finds the highest open balance, and obeys "enter nothing".
  4. *Batch Ingestion*: `ENTER_INVOICES` with `count=2` handles multi-item entry.
  5. *Refusal*: Handles nonexistent entities (`Cyberdyne Systems`) cleanly.
- **Code Pointer**: [`agent/planner.py:classify_task_intent()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/planner.py#L10-L68), [`evals/results.md`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/evals/results.md).

---

### Q9: "How does your evaluation harness verify outcomes without the agent cheating?"
- **Answer**: The sandbox exposes a test-only debug endpoint at `GET /api/debug/state` on both ports that returns the exact raw database records. The evaluation harness in `evals/run.py` queries this endpoint after every task run as a ground-truth oracle. The agent itself has no access to `/api/debug/state`, does not know about it in its prompt, and must rely entirely on user-facing web pages.
- **Code Pointer**: [`evals/run.py:fetch_debug_state()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/evals/run.py#L22-L34), [`sandbox/finance_system/app.py:get_debug_state()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/sandbox/finance_system/app.py#L292-L313).

---

### Q10: "What happens if a user submits a duplicate invoice that already exists in the finance system?"
- **Answer**: The Finance ERP enforces database-level uniqueness on `(vendor, invoice_no)` and responds with HTTP 409 Conflict. Rather than treating this as a crash, `AutonomousTaskWorker` identifies `is_duplicate = True`, logs a remediation record ("Handled duplicate rejection: Invoice was already registered"), and transitions directly to independent verification to audit that the existing record matches ground truth.
- **Code Pointer**: [`sandbox/finance_system/app.py:add_payable()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/sandbox/finance_system/app.py#L237-L255), [`agent/runner.py:AutonomousTaskWorker.run()`](file:///c:/Users/jraje/OneDrive/Desktop/vscode/CentrAlign_task/agent/runner.py#L400-L415).
