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
