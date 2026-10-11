# Technical & Architectural Decisions Log

This document records key technical choices, alternatives evaluated, trade-offs, and rationale as the project evolves.

---

### DEC-0001: Focus on Narrow Working Prototype over Broad Mocked System
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: The problem asks for an Autonomous AI Task Worker capable of taking a natural language business task (e.g., invoice discovery, extraction, internal system entry, verification, and evidence reporting). Evaluation criteria reward genuine execution reliability and ground-truth verification over superficial breadth with mocked components.
- **Decision**: Build a production-grade, narrow vertical slice that genuinely executes against local files, a real headless/visual browser or API, and a simulated internal business portal. Every state transition will be verified against ground truth rather than LLM assumptions.
- **Consequences**: We will invest in clean tool harnesses, deterministic ground-truth verification functions, structured run traces, and clear recovery paths rather than building shallow wrappers for dozens of unused tools.

---

### DEC-0002: Project Organization and Milestone Governance
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: Autonomous agents require strict discipline in development to ensure testability, safety, and transparent progress tracking.
- **Decision**: Enforce strict milestone rules:
  1. Update `PROGRESS.md` after every milestone.
  2. Update `README.md` if setup or usage changes.
  3. Append to `DECISIONS.md` for every architectural choice.
  4. Make atomic Git commits with descriptive messages and push to `origin main`.
  5. Never commit secrets.
  6. Never claim a feature works unless actively run and verified.
  7. Maintain honesty about hardcoded or mocked components.
- **Consequences**: Traceable development history, high engineering hygiene, and zero hallucinated claims.

---

### DEC-0003: FastAPI and Jinja2 for Simulated Corporate Apps
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: We need two distinct web applications running on separate ports: an external Vendor Portal (8001) and an Internal Finance ERP (8002).
- **Decision**: Use Python with FastAPI and Jinja2 templates without complex JavaScript frontend frameworks (React/Vue).
- **Rationale**:
  - FastAPI provides native ASGI performance, async endpoints, clean cookie-based session management, and OpenAPI schemas.
  - Plain server-rendered HTML forms and tables match traditional corporate portals and allow browser automation tools (Playwright / BeautifulSoup / HTTP clients) to inspect real DOM trees and standard form submissions.
  - Zero frontend build step (`npm run build`, webpack) eliminates build flakiness and keeps repo setup instantaneous.

---

### DEC-0004: ReportLab for Generating Authentic PDF Invoices
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: The task requires handling downloadable invoice PDFs. Fake text files disguised as `.pdf` would fail realistic PDF parser tools.
- **Decision**: Use `reportlab` in `scripts/seed.py` to generate authentic, multi-section binary PDF documents (`%PDF-1.4`) with headers, line item tables, amounts, dates, and remittance instructions.
- **Consequences**: Enables the AI worker to genuinely extract amounts and due dates either from the web DOM or by downloading and parsing real PDF document binaries.

---

### DEC-0005: SQLite Persistence and Enforced Duplicate Prevention
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: The agent must record payable entries into the internal system, which must persist across requests and support verification. Real financial systems also reject duplicate invoices.
- **Decision**: Use SQLite (`sandbox/data/finance.db`) with unique constraints on `(vendor, invoice_no)`. The application layer returns HTTP 409 Conflict with clear error messages when duplicate invoices are submitted.
- **Consequences**: Provides tamper-evident ground-truth persistence. Enables automated test suites to inspect the SQLite file directly and verifies the agent's ability to handle conflict responses.

---

### DEC-0006: Deliberate DOM Generalization Test (Table vs Card Layout)
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: AI agents often overfit to identical HTML table structures and break when encountering different UI paradigms.
- **Decision**: Render 4 vendors using standard HTML `<table>` elements and 1 vendor (`Vertex Analytics`) using a CSS flex/grid card structure (`.invoice-card`, `.invoice-meta-row`, without `<table>` tags).
- **Consequences**: Tests whether the agent can generalize semantic reasoning (locating dates and amounts in non-tabular layouts) rather than relying on fixed DOM selector heuristics.

---

### DEC-0007: Controllable Real-World Chaos and Ground-Truth API Isolation
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: Real-world web applications suffer from slow responses, transient 500 server errors, and session expiries. At the same time, test suites need an objective oracle to verify agent correctness.
- **Decision**:
  - Provide environment-variable chaos toggles (`CHAOS_SLOW_PAGES`, `CHAOS_500_ON_SUBMIT`, `CHAOS_SESSION_EXPIRY`), default OFF for predictability, but toggleable for robustness benchmarking.
  - Provide `GET /api/debug/state` endpoints on both apps explicitly labeled for test harnesses only. The agent's prompt and tools will restrict it to user-facing web interfaces.
- **Consequences**: Clean separation of concerns between agent perception and external evaluation harnesses.

---

### DEC-0008: Decoupled Independent Verification vs Self-Reported Success
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: Agents commonly hallucinate task completion by confusing their intended actions with actual system state transitions.
- **Decision**: Introduce a distinct `IndependentVerifier` class that executes after the agent signals completion. The verifier opens an isolated browser session, connects directly to the Internal Finance System, queries the SQLite ledger, and compares extracted source invoice values against recorded destination values across all four dimensions (vendor, invoice #, amount, due date).
- **Consequences**: The system yields an objective **PASS / FAIL / UNCERTAIN** determination. The final report explicitly contrasts what the agent *claimed* with what the verifier *proved*.

---

### DEC-0009: Exponential Backoff, Stagnant Progress, and Loop Detection Architecture
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: Network hiccups, transient 500 errors, and infinite loops are primary failure modes in autonomous computer-use agents.
- **Decision**: Implement `FailureManager` to detect:
  1. Identical action repetitions (capped at 3 consecutive identical actions to raise `LoopDetectedError`).
  2. Stagnant progress (detecting identical DOM state hashes following write operations).
  3. Transient network or HTTP 500 errors (retrying with exponential backoff $base \times 2^{retry}$, capped at 3 retries).
- **Consequences**: Prevents runaway token burn or frozen loops while providing resilience against flakiness.

---

### DEC-0010: Risk-Tiered Human Approval Gate and Prompt-Injection Defense
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: Autonomous agents performing financial actions (creating payables) pose real business risks if unconstrained. Ingesting untrusted third-party web content also introduces prompt injection risks.
- **Decision**:
  - Enforce a 3-tier risk classification: `READ_ONLY`, `REVERSIBLE_WRITE`, and `IRREVERSIBLE_FINANCIAL_WRITE`. Any financial disbursement or payable creation requires human confirmation unless `--auto-approve` is explicitly passed.
  - Ambiguous tasks prompt the user for clarification rather than making ungrounded assumptions.
  - Web and PDF contents are delimited within `<untrusted_web_content>` tags, and credentials can only be loaded from environment variables, preventing credential leakage or prompt hijacking.
- **Consequences**: Production-grade safety alignment and auditability.

---

### DEC-0011: Mid-Task Session Timeout Self-Healing
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: Enterprise portals routinely expire user sessions after periods of inactivity or request quotas. Traditional scripts crash when encountering unexpected redirect to `/login`.
- **Decision**: Implement proactive login detection in `BrowserClient` and `AutonomousTaskWorker`. When a session expiration is detected mid-task, the worker pauses the current step, re-authenticates using environment credentials, and resumes the pending action seamlessly.
- **Consequences**: High task completion autonomy across multi-step flows without requiring user intervention for simple session timeouts.

---

### DEC-0012: Task Generalization via Semantic Intent Planning Without Hacks
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: An autonomous agent must solve diverse, unseen task instructions (aggregation, cross-vendor comparison, batch ingestion, impossible entity rejection) without modifying agent code or injecting task-specific company hacks.
- **Decision**: Implement `TaskPlanner.classify_task_intent()` which decomposes natural language into general operational semantics: intent (`ENTER_INVOICES`, `REPORT_OVERDUE`, `REPORT_HIGHEST_UNPAID`, `REPORT_GENERAL`), entity query, target quantity, and write requirements. The runner executes the exact same underlying browser tools and verification pipeline for all tasks.
- **Consequences**: Zero overfitting to specific company names or single invoice structures; genuine general business task automation.

---

### DEC-0013: Ground-Truth Debug Oracle Isolation in Evaluation Harness
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: Benchmarking requires validating whether an agent actually achieved the intended ground truth across various chaos configurations.
- **Decision**: Build `evals/tasks.yaml` and `evals/run.py` where the harness alone queries `/api/debug/state` to objectively audit database states and verify task success. The autonomous agent remains strictly forbidden from querying debug endpoints, relying only on user-facing DOM and database verification.
- **Consequences**: 100% transparent and objective evaluation metrics without circular self-reporting or evaluation contamination.

---

### DEC-0014: Non-LLM Component Unit Testing Architecture
- **Date**: 2026-10-11
- **Status**: Accepted
- **Context**: Core reliability mechanisms (risk classification, loop detection, exponential backoff, verifier field comparison, date filtering) must be deterministic, highly reliable, and tested independently of stochastic LLM outputs.
- **Decision**: Build a dedicated unit test suite (`tests/test_unit_core.py`) in `pytest` isolating non-LLM logic. Test mathematical backoff progressions ($base \times 2^r$), three-strike loop triggers, state-hash stagnant progress, exact vs. mismatched verifier comparisons, and PDF regex extraction.
- **Consequences**: Guarantees zero regressions in core safety and reliability logic during refactors, providing high test velocity (19 unit tests executing in <0.6s).
