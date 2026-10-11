# Autonomous AI Task Worker

> An autonomous AI computer-use agent that takes high-level natural language instructions, plans, interacts with digital tools (browser, filesystem, APIs, internal business applications), verifies ground-truth outcomes, and reports structured evidence.

**Status: in progress**

---

## Overview
Built as a submission for the CentrAlign AI "Autonomous AI Task Worker" internship problem.

The worker is designed to complete complex multi-system workflows such as:
> *"Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done."*

### Key Evaluation Criteria Addressed
- **Autonomy & Planning:** Decomposes natural language instructions, identifies target entities, compares invoice dates chronologically, and adapts dynamically.
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

### Layout Generalization
The agent handles both standard table layouts (Acme, Global Logistics, Nexus, Prime) and non-standard card grid layouts (`Vertex Analytics`) without requiring fixed CSS selectors.

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

Run the full pytest suite (7/7 tests passing):
```bash
pytest -v
```

Tests include:
- `test_vendor_portal_auth_and_navigation`
- `test_finance_system_auth_and_payables_lifecycle`
- `test_happy_path_with_independent_verification`
- `test_odd_layout_generalization_vertex_analytics`
- `test_chaos_recovery_and_duplicate_resilience`
- `test_human_clarification_on_ambiguous_task`
- `test_human_approval_rejection_safety`

See [PROGRESS.md](PROGRESS.md) for milestone tracking and [DECISIONS.md](DECISIONS.md) for technical architecture rationale.
