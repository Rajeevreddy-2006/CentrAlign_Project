# Autonomous AI Task Worker

> An autonomous AI computer-use agent that takes high-level natural language instructions, plans, interacts with digital tools (browser, filesystem, APIs, internal business applications), verifies ground-truth outcomes, and reports structured evidence.

**Status: completed**

---

## Overview
Built as a submission for the CentrAlign AI "Autonomous AI Task Worker" internship problem.

The worker is designed to complete complex multi-system workflows such as:
> *"Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done."*

### Key Evaluation Criteria Addressed
- **Autonomy & Generalization:**
  - Solves diverse business workflows through the **exact same unchanged agent code**:
    1. *Standard Invoice Entry*: Discovers invoices, parses tables, downloads PDFs, enters into ERP, and audits.
    2. *DOM Layout Generalization*: Handles unstructured card grids (`Vertex Analytics`) dynamically.
    3. *Overdue Invoices Aggregation*: Identifies overdue invoices for a vendor, sums balances, and returns analytical reports without modifying destination databases.
    4. *Cross-Vendor Analytical Comparison*: Audits all vendors in the directory, compares unpaid amounts, identifies the vendor with the highest unpaid balance, and complies with "enter nothing, just report" directives.
    5. *Multi-Invoice Ingestion*: Processes batches (e.g. "enter top 2 most recent") with individual human approval gates and multi-record ground-truth audits.
    6. *Ambiguous / Impossible Entity Handling*: Gracefully halts and reports clear refusal when nonexistent entities are requested (`Cyberdyne Systems`) rather than hallucinating actions.
- **Reliability & Failure Recovery:**
  - Detects network timeouts, HTTP 500 errors, DOM error banners, element absence, action loops (3 identical attempts), and stagnant progress.
  - Automatically recovers from transient errors via **exponential backoff** ($base \times 2^{retry}$).
  - Automatically recovers from **mid-task session timeouts** by recognizing login redirects, re-authenticating with authorized environment credentials, and resuming the in-flight action.
  - Gracefully recovers from duplicate submissions (HTTP 409) by recognizing pre-existing records and auditing them.
- **Independent Verification (Crucial):**
  - Completely decouples outcome verification from the agent's internal thoughts.
  - An independent `Verifier` step opens an isolated session, inspects the destination ERP database directly, compares all four fields (Vendor, Invoice #, Amount, Due Date), and issues an authoritative **PASS / FAIL / UNCERTAIN** report with ground-truth evidence.
  - Never claims success unless objectively confirmed in the destination database.
- **Safety & Human-in-the-Loop (HITL):**
  - **Risk Classification:** Classifies actions as `READ_ONLY`, `REVERSIBLE_WRITE`, or `IRREVERSIBLE_FINANCIAL_WRITE`.
  - Financial writes (creating payables) require human authorization unless `--auto-approve` is passed.
  - **Ambiguity Escalation:** Halts and prompts the user for clarification when multiple vendors match or target entities are unclear, avoiding hallucinated actions.
  - **Security Quarantine:** Enforces a strict domain allowlist (`localhost:8001`, `localhost:8002`), forbids credentials outside environment variables, and wraps untrusted web/PDF content in `<untrusted_web_content>` prompt-injection defense boundaries.

---

## Simulated Environment (Sandbox)

The sandbox provides two independent, fully functional web applications running on separate ports:

| Service | Port | Description | Default Credentials |
| :--- | :--- | :--- | :--- |
| **Vendor Portal** | `http://localhost:8001` | External portal listing 5 vendors and 22 invoices across dates, with downloadable PDFs and layout variations. | `vendor_admin` / `vendor_pass123` |
| **Internal Finance System** | `http://localhost:8002` | Internal ERP with accounts payable ledger, new payable entry form, duplicate rejection, and SQLite persistence. | `finance_user` / `finance_pass123` |

### Seeding Data
Generate the vendor catalog, SQLite database, and realistic downloadable PDF invoices:
```bash
python scripts/seed.py
```

### Running the Sandbox
```bash
# Cross-platform runner:
python scripts/run_sandbox.py

# Or on Linux/macOS:
./scripts/run_sandbox.sh
```

---

## Running the Autonomous Task Worker

### Standard Execution (Interactive Human Gate)
```bash
python -m agent.cli --task "Find the latest invoice from Acme Cloud Corp, extract the amount and due date, enter it into our internal system, and tell me once it is done."
```

### Automated / Headless Execution (`--auto-approve`)
```bash
python -m agent.cli --task "Find the latest invoice from Vertex Analytics, extract the amount and due date, enter it into our internal system, and tell me once it is done." --auto-approve
```

---

## Evaluation Benchmark Suite (`evals/`)

The evaluation harness rigorously benchmarks the worker across 7 diverse tasks with varying chaos levels. The harness queries isolated ground-truth debug oracle endpoints (`/api/debug/state`), which the autonomous agent is forbidden from accessing.

Run the evaluation benchmark:
```bash
python -m evals.run
```

Benchmark output is logged transparently to [`evals/results.md`](evals/results.md):

| Task ID & Name | Chaos Mode | Success Rate | Avg Steps | Avg Retries | Approvals | Avg Runtime | Est. Tokens |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standard Latest Invoice Entry (Table Layout)** | `OFF` | **100%** | 8.0 | 0.0 | 1.0 | 0.29s | 3,600 |
| **Card Layout Latest Invoice Entry (Cards Layout)** | `OFF` | **100%** | 8.0 | 0.0 | 1.0 | 0.23s | 3,600 |
| **Overdue Invoices Aggregation & Total Reporting** | `OFF` | **100%** | 4.0 | 0.0 | 0.0 | 0.09s | 1,800 |
| **Cross-Vendor Highest Unpaid Amount Comparison** | `OFF` | **100%** | 8.0 | 0.0 | 0.0 | 0.15s | 3,600 |
| **Multi-Invoice Ingestion (Top 2 Most Recent)** | `OFF` | **100%** | 9.0 | 0.0 | 2.0 | 0.35s | 4,050 |
| **Impossible Task: Nonexistent Vendor Escalation** | `OFF` | **100%** | 3.0 | 0.0 | 0.0 | 0.07s | 1,350 |
| **Chaos Mode Resilience: Network Faults & Latency** | `ON` | **100%** | 8.0 | 0.0 | 1.0 | 0.23s | 3,600 |

---

## Demonstrating Chaos & Failure Recovery

Run the live chaos demonstration script to witness the agent recovering from deliberate real-world faults:
```bash
python scripts/demonstrate_chaos_and_recovery.py
```

This test actively verifies:
1. **Transient 500 Errors & Exponential Backoff:** Retries failed submissions after exponential delay.
2. **Session Expiry Self-Healing:** Catches mid-task session invalidation, re-authenticates to the respective portal, and completes the action.
3. **Duplicate Submission Handling:** Detects 409 Conflict, recovers without crashing, and verifies ledger persistence.
4. **Human Clarification on Ambiguity:** Prompts the user with candidate vendors when instructions are ambiguous.
5. **Human Approval Rejection:** Safely aborts financial transactions when the user rejects authorization.

Sample verified execution trace: [`runs/sample/sample_verified_chaos_report.md`](runs/sample/sample_verified_chaos_report.md)

---

## Automated Test Suite

Run the full pytest suite (**26/26 tests passing**):
```bash
pytest -v
```

The test suite covers:
- **Core Non-LLM Unit Tests** ([`tests/test_unit_core.py`](tests/test_unit_core.py)):
  - Risk classification (`READ_ONLY`, `REVERSIBLE_WRITE`, `IRREVERSIBLE_FINANCIAL_WRITE`)
  - Loop detection (3-action threshold) and stagnant progress (state hashes)
  - Exponential backoff calculation and transient vs. fatal retry boundaries
  - Independent verifier field-matching and discrepancy detection
  - Natural language task planning and entity extraction
  - Authentic PDF regex extraction
- **Resilience & Safety Suite** ([`tests/test_agent_resilience.py`](tests/test_agent_resilience.py)):
  - End-to-end happy path with ground-truth verification
  - DOM card-layout generalization
  - Chaos recovery and duplicate handling
  - Human clarification on ambiguous supplier names
  - Human rejection safety
- **Sandbox Infrastructure Suite** ([`tests/test_sandbox.py`](tests/test_sandbox.py)):
  - Vendor portal and finance ERP lifecycle

See [PROGRESS.md](PROGRESS.md) for milestone tracking and [DECISIONS.md](DECISIONS.md) for technical architecture rationale.
