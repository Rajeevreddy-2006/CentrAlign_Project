# Autonomous AI Task Worker

> An autonomous AI computer-use agent that takes high-level natural language instructions, plans, interacts with digital tools (browser, filesystem, APIs, internal business applications), verifies ground-truth outcomes, and reports structured evidence.

**Status: in progress**

---

## Overview
Built as a submission for the CentrAlign AI "Autonomous AI Task Worker" internship problem.

The worker is designed to complete complex multi-system workflows such as:
> *"Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done."*

### Key Tenets
- **Autonomy & Planning:** Decomposes high-level instructions into executable steps with adaptive replanning.
- **Genuine Execution:** Interacts with real, live web services and file systems rather than mocked responses.
- **Ground-Truth Verification:** Never assumes tool execution succeeded; inspects actual state transitions in the destination database.
- **Reliability & Error Recovery:** Recovers from network glitches, session timeouts, and duplicate submissions.
- **Safety & HITL (Human-in-the-Loop):** Escalates for user clarification/approval before executing destructive or high-risk actions.
- **Auditability:** Delivers concise summaries accompanied by verifiable artifacts (e.g., downloaded PDFs, transaction receipts).

---

## Simulated Environment (Sandbox)

The sandbox provides two independent, fully functional web applications running on separate ports to simulate a realistic corporate ecosystem:

| Service | Port | Description | Default Credentials |
| :--- | :--- | :--- | :--- |
| **Vendor Portal** | `http://localhost:8001` | External portal listing 5 vendors and 22 invoices across dates, with downloadable PDFs and layout variations. | `vendor_admin` / `vendor_pass123` |
| **Internal Finance System** | `http://localhost:8002` | Internal ERP with accounts payable ledger, new payable entry form, duplicate rejection, and SQLite persistence. | `finance_user` / `finance_pass123` |

### Seeding Data
Generate the vendor catalog, SQLite database, and realistic downloadable PDF invoices:
```bash
# Activate virtual environment
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate

# Run seed script
python scripts/seed.py
```

### Running the Sandbox

#### Option A: Cross-Platform Python Runner (Recommended on Windows/Mac/Linux)
```bash
python scripts/run_sandbox.py
```

#### Option B: Shell Script (Linux / macOS / WSL)
```bash
chmod +x scripts/run_sandbox.sh
./scripts/run_sandbox.sh
```

Both servers will start concurrently:
- Vendor Portal: [http://localhost:8001](http://localhost:8001)
- Internal Finance ERP: [http://localhost:8002](http://localhost:8002)

---

## Real-World Messiness & Chaos Testing

To test the worker's resilience and error recovery, the sandbox supports configurable chaos toggles in `.env` (default: **OFF**):

```env
# Master chaos switch
CHAOS_MODE=false

# Latency injection
CHAOS_SLOW_PAGES=false
CHAOS_DELAY_SECONDS=1.5

# Transient server errors on form submission
CHAOS_500_ON_SUBMIT=false
CHAOS_ERROR_RATE=0.35

# Session timeouts (forces agent re-login)
CHAOS_SESSION_EXPIRY=false
CHAOS_SESSION_MAX_REQUESTS=3

# Business rule: Rejects duplicate invoice submissions (Default: ON)
ENFORCE_DUPLICATE_CHECK=true
```

### Deliberate Layout Variations
- Standard vendors (`Acme Cloud Corp`, `Global Logistics Ltd`, `Nexus Software Solutions`, `Prime Hardware & Supplies`) render a standard HTML table.
- `Vertex Analytics` renders an alternative **card grid layout** (`invoices-grid`) with different DOM tags to verify the agent doesn't rely on rigid, hardcoded CSS selectors.

### Independent Ground-Truth Debug Endpoints
For testing harnesses and verification suites to objectively assess agent success without relying on agent self-reporting:
- `GET http://localhost:8001/api/debug/state`: Ground-truth catalog of vendors and mathematically sorted "latest" invoice.
- `GET http://localhost:8002/api/debug/state`: Ground-truth SQLite database ledger records.

> **Note:** The autonomous agent is strictly forbidden from using `/api/debug/state`. These endpoints exist solely for test harnesses.

---

## Running Automated Tests

Run the complete test suite (unit tests and live socket integration):
```bash
# Run pytest test suite
pytest tests/test_sandbox.py -v

# Run live socket verification against real running servers
python scripts/verify_live_sandbox.py
```

See [PROGRESS.md](PROGRESS.md) for milestone tracking and [DECISIONS.md](DECISIONS.md) for technical architecture rationale.
