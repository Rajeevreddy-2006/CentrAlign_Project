# Manual Screen Recording & Presentation Guide

If you prefer to record the live demo yourself using **Windows Game Bar (Win + G)** or **OBS Studio**, follow this step-by-step procedure to capture a clean, professional demonstration.

---

## 1. Pre-Recording Setup & Checklist

- [ ] **Display Resolution**: Set screen scaling to 100% or 125% at 1920x1080 or 1280x720.
- [ ] **Clean Desktop**: Close all non-essential applications, browser tabs, and chat windows.
- [ ] **Mute Notifications**: Enable Windows Focus Assist ("Do Not Disturb") to prevent notification popups.
- [ ] **Terminal Layout**: Open your terminal (PowerShell) with font size ~16pt, split or positioned side-by-side with your browser window.
- [ ] **Security**: Ensure `.env` is not open on screen. The agent code never displays passwords on screen.

---

## 2. Step-by-Step Recording Sequence

### Step 0: Ensure Sandbox Apps Are Running
In Terminal 1:
```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Reseed database and start dual sandbox servers
python scripts/seed.py
python scripts/run_sandbox.py
```
Leave Terminal 1 running. Open a browser window to `http://localhost:8001` (Vendor Portal) and `http://localhost:8002` (Finance ERP).

---

### Step 1: Scene 1 — Main Task (Standard Table Layout)
In Terminal 2:
```bash
python -m agent.cli --task "Find the latest invoice from Acme Cloud Corp, extract the amount and due date, enter it into our internal system, and tell me once it is done." --auto-approve
```
- **What to show**: The terminal output discovering `INV-ACME-1004`, downloading the PDF, and submitting the payable.
- **Refresh Browser**: Show `http://localhost:8002/payables` to display the new entry in the table. Point out the `[INDEPENDENT VERIFICATION LAYER] Verification Status: PASS`.

---

### Step 2: Scene 2 — Resilience & Chaos Mode (Transient 500s & Session Expiry)
In Terminal 2:
```bash
# Enable live chaos injection and run demonstration
python scripts/demonstrate_chaos_and_recovery.py
```
- **What to show**: Point out:
  1. `[Transient Error] Retrying (1/3) after 2.0s backoff...`
  2. `[Session Expired] Re-authenticating... [Re-authenticated]`
  3. `[Duplicate Recognized] Handled duplicate rejection`
  4. Final verification PASS.

---

### Step 3: Scene 3 — Human-in-the-Loop Safety & Clarification
In Terminal 2:
```bash
python -m agent.cli --task "Find the latest invoice from a supplier, extract the amount and due date, enter it into our internal system, and tell me once it is done."
```
- **What to show**:
  1. The agent stops and asks for clarification: `Which vendor should be processed? [1] Acme Cloud Corp [2] Global Logistics Ltd...`
  2. Enter `1`.
  3. The agent stops at the Risk Gate: `[HUMAN APPROVAL REQUIRED]: FINANCIAL ACTION DETECTED. Authorize this financial write into the internal ERP system? (yes/no):`
  4. Type `yes` and press Enter. Shows verified entry.

---

### Step 4: Scene 4 — Task Generalization (Read-Only Overdue Report)
In Terminal 2:
```bash
python -m agent.cli --task "List all invoices from Acme Cloud Corp that are overdue and tell me the total."
```
- **What to show**: The agent decomposes the intent as read-only, locates `INV-ACME-1003` ($2,150.00), reports the total, and performs **zero database writes**.

---

### Step 5: Scene 5 — Card-Grid Layout & Decoupled Verification
In Terminal 2:
```bash
python -m agent.cli --task "Find the latest invoice from Vertex Analytics, extract the amount and due date, enter it into our internal system, and tell me once it is done." --auto-approve
```
- **What to show**: Open `http://localhost:8001/vendors/vertex-analytics` in the browser to show the cards grid layout (not a table). Show that the agent correctly parses `INV-VA-204` ($4,100.00) and passes verification.

---

### Step 6: Scene 6 — Evaluation Benchmark
In Terminal 2:
```bash
python -m evals.run
```
- **What to show**: The final evaluation results table showing a 100% success rate across all 7 tasks.

---

## 3. Saving & Submitting
- If using **Windows Game Bar** (`Win + G`), find your recording in `C:\Users\<user>\Videos\Captures`.
- If the file is > 50 MB, compress using ffmpeg:
  ```bash
  .venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe -i input.mp4 -vcodec libx264 -crf 26 -preset fast demo/demo.mp4
  ```
- Upload `demo/demo.mp4` to Google Drive or Loom and include the link in your submission.
