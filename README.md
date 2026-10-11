# Autonomous AI Task Worker

> An autonomous AI computer-use agent that takes high-level natural language instructions, plans, interacts with digital tools (browser, filesystem, APIs, internal business applications), verifies ground-truth outcomes, and reports structured evidence.

**Status: in progress**

---

## Overview
Built as a submission for the CentrAlign AI "Autonomous AI Task Worker" internship problem.

The worker prioritizes:
- **Autonomy & Planning:** Goal decomposition, execution loop, reactive replanning.
- **Tooling:** Browser automation, file manipulation, structured API / simulated enterprise app integration.
- **Verification:** Never assuming tool calls succeeded without checking ground-truth state changes.
- **Safety & HITL (Human-in-the-loop):** Asking user approval for irreversible/uncertain actions.
- **Auditability:** Concise summary generation backed by artifact-level evidence.

See [PROGRESS.md](PROGRESS.md) for milestone tracking and [DECISIONS.md](DECISIONS.md) for architectural trade-offs.
