# Autonomous AI Task Worker - Live Demo Execution Report

**Generated At:** 2026-10-12 13:43:16
**Final Video Path:** `C:\Users\jraje\OneDrive\Desktop\vscode\CentrAlign_task\demo\demo.mp4` (2.61 MB)

## Scene Execution Audit Table

| Scene ID | Title | Chaos Mode | Steps | Retries | Verification | Result |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `scene_1_main` | **Scene 1: Autonomous Invoice Discovery & Entry (Chaos OFF)** | OFF | 8 | 0 | PASS | **PASS** |
| `scene_2_resilience` | **Scene 2: Failure Recovery & Chaos Resilience (Chaos ON)** | ON | 8 | 0 | PASS | **PASS** |
| `scene_3_hitl` | **Scene 3: Human-in-the-Loop Ambiguity Clarification & Risk Gating** | OFF | 8 | 0 | PASS | **PASS** |
| `scene_4_generalization` | **Scene 4: Task Generalization - Overdue Invoices Aggregation (Read-Only)** | OFF | 4 | 0 | PASS | **PASS** |
| `scene_5_verification` | **Scene 5: Independent Verification & DOM Layout Generalization (Cards Grid)** | OFF | 8 | 0 | PASS | **PASS** |

---

### Scene Task Prompts & Ground Truth Outcomes

#### Scene 1: Autonomous Invoice Discovery & Entry (Chaos OFF)
- **Task Prompt:** `Find the latest invoice from Acme Cloud Corp, extract the amount and due date, enter it into our internal system, and tell me once it is done.`
- **Steps Executed:** 8 (Retries: 0)
- **Audit Details:** Verification PASS: Ground-truth record #58 confirmed in Finance ERP. Vendor: Acme Cloud Corp, Invoice: INV-ACME-1004, Amount: $2,490.75, Due Date: 2026-10-30.

#### Scene 2: Failure Recovery & Chaos Resilience (Chaos ON)
- **Task Prompt:** `Find the latest invoice from Global Logistics Ltd, extract the amount and due date, enter it into our internal system, and tell me once it is done.`
- **Steps Executed:** 8 (Retries: 0)
- **Audit Details:** Verification PASS: Ground-truth record #59 confirmed in Finance ERP. Vendor: Global Logistics Ltd, Invoice: INV-GL-505, Amount: $7,250.00, Due Date: 2026-11-02.

#### Scene 3: Human-in-the-Loop Ambiguity Clarification & Risk Gating
- **Task Prompt:** `Find the latest invoice from a supplier, extract the amount and due date, enter it into our internal system, and tell me once it is done.`
- **Steps Executed:** 8 (Retries: 0)
- **Audit Details:** Verification PASS: Ground-truth record #60 confirmed in Finance ERP. Vendor: Acme Cloud Corp, Invoice: INV-ACME-1004, Amount: $2,490.75, Due Date: 2026-10-30.

#### Scene 4: Task Generalization - Overdue Invoices Aggregation (Read-Only)
- **Task Prompt:** `List all invoices from Acme Cloud Corp that are overdue and tell me the total.`
- **Steps Executed:** 4 (Retries: 0)
- **Audit Details:** Overdue audit verified: 1 overdue invoices totaled $2,150.00.

#### Scene 5: Independent Verification & DOM Layout Generalization (Cards Grid)
- **Task Prompt:** `Find the latest invoice from Vertex Analytics, extract the amount and due date, enter it into the internal finance system, and notify me.`
- **Steps Executed:** 8 (Retries: 0)
- **Audit Details:** Verification PASS: Ground-truth record #61 confirmed in Finance ERP. Vendor: Vertex Analytics, Invoice: INV-VA-204, Amount: $4,100.00, Due Date: 2026-10-15.

