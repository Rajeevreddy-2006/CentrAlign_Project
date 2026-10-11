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
