# Demo Video Spoken Narration Script

**Duration:** ~3:30 to 4:00 minutes  
**Format:** First-person, authentic presentation matching live scenes in `demo/demo.mp4`.

---

### [0:00 - 0:15] Title Slide & Introduction
*(Visual: Title Card displaying project title and key features)*

> "Hi everyone, I'm presenting my submission for the CentrAlign Autonomous AI Task Worker internship challenge. 
> Enterprise robotic automation often fails when systems are messy: sessions expire, pages throw random 500 errors, or invoice layouts change. 
> I built a resilient, general-purpose computer-use worker that plans, executes, self-heals, and independently verifies business tasks across corporate portals."

---

### [0:15 - 1:00] Scene 1: Main Autonomous Task (Table Layout, Chaos OFF)
*(Visual: Browser navigates to Vendor Portal, selects Acme Cloud, finds INV-ACME-1004, submits to Finance ERP, and audits)*

> "In Scene 1, we see the agent tackle the core task: finding the latest invoice from Acme Cloud Corp and entering it into our Internal Finance system. 
> Notice that the agent doesn't just grab the top row of the table. It parses every issue date across the rows, strictly sorting chronologically to isolate invoice `INV-ACME-1004`. 
> It downloads the authentic PDF statement, cross-validates the amount—$2,490.75—and due date, navigates to our Finance ERP, fills out the payable form, and submits the entry.
> Once complete, our independent verification layer audits the ground-truth SQLite database to confirm the record exists."

---

### [1:00 - 1:50] Scene 2: Resilience & Chaos Recovery (Chaos ON)
*(Visual: Global Logistics run, transient 500 error on submit, exponential backoff, auto-relogin, successful recovery)*

> "Scene 2 demonstrates real-world reliability with chaos mode turned on. 
> Here, our sandbox injects latency, mid-task session expirations, and a 70% transient 500 database lock on submission. 
> Watch how the agent behaves: when the 500 error strikes, the agent doesn't crash or loop. It classifies the error as transient, computes an exponential backoff delay, and retries. 
> When the portal expires the session, the worker detects the login redirect, re-authenticates using environment credentials, and resumes the exact in-flight action seamlessly. 
> It achieves a verified PASS even under severe infrastructure faults."

---

### [1:50 - 2:30] Scene 3: Human-in-the-Loop Safety & Clarification
*(Visual: Task prompt "Find latest invoice from a supplier" -> clarifies vendor -> prompts human approval for financial write)*

> "In Scene 3, we demonstrate safety and Human-in-the-Loop governance. 
> Autonomous agents should not guess in high-stakes workflows. When given an ambiguous prompt like 'Find the latest invoice from a supplier', the agent detects ambiguity, halts, and requests user clarification with valid candidates.
> Furthermore, every action is evaluated by our Risk Classifier. Navigations and reads are zero-friction, but financial writes to `/payables/add` are classified as `IRREVERSIBLE_FINANCIAL_WRITE`. 
> The worker stops and prompts the human for explicit approval before any money or payable is committed to the books."

---

### [2:30 - 3:10] Scene 4: Multi-Task Generalization (Read-Only Analytical Task)
*(Visual: Task prompt "List all invoices from Acme that are overdue and tell me the total" -> reports sum without writes)*

> "Scene 4 proves generalization across different business tasks using the exact same unchanged codebase. 
> Here, the user asks for an analytical report: 'List all invoices from Acme that are overdue and tell me the total.' 
> The task planner classifies this as a read-only aggregation. The worker inspects the invoices, filters those with overdue status or dates prior to our reference cutoff, identifies `INV-ACME-1003` for $2,150, and returns the total. 
> Crucially, it obeys the read-only constraint and performs zero unauthorized database writes."

---

### [3:10 - 3:45] Scene 5: Independent Verification & Card-Grid Generalization
*(Visual: Vertex Analytics card grid layout -> extracts INV-VA-204 -> submits to ERP -> shows verifier audit)*

> "In Scene 5, we test layout generalization and our independent verifier. 
> Vertex Analytics doesn't use HTML tables; its invoices are rendered in an unstructured card grid layout. 
> The agent dynamically extracts the data without brittle CSS assumptions. 
> More importantly, look at the verification banner: the verifier is completely decoupled from the agent's internal monologue. 
> It spawns in an isolated session, inspects the SQLite database, and matches Vendor, Invoice Number, Amount, and Due Date. It issues an authoritative PASS only because ground truth matches."

---

### [3:45 - 4:15] Architecture & Evaluation Summary (Conclusion Slides)
*(Visual: Architecture Slide and Benchmark Table Slide from evals/results.md)*

> "Wrapping up with the architecture: we have an intent planner, a session-aware DOM client, a 3-strike loop detector, a risk classifier, and an independent verifier. 
> In our evaluation harness across 7 diverse tasks, the worker achieved a 100% verified pass rate. 
> To be completely honest about limitations: our browser client currently uses session HTTP with BeautifulSoup, meaning client-side React SPA hydration isn't supported yet. 
> If I had two more weeks, I would add a dual-engine Playwright fallback and Gemini Flash multimodal visual screenshot inspection. 
> Thank you!"
