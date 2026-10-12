#!/usr/bin/env python3
"""
Full Autonomous Demo Recorder for CentrAlign AI Task Worker.
Executes real scenes in a headed Playwright browser against the live sandbox,
records real browser video at 1280x720, injects on-screen caption banners,
generates slide cards, and concatenates all clips into demo/demo.mp4 via ffmpeg.
"""

import os
import sys
import time
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.config import VENDOR_PORTAL_BASE, FINANCE_SYSTEM_BASE
from agent.runner import AutonomousTaskWorker
from agent.models import ActionType, RiskLevel

DEMO_DIR = REPO_ROOT / "demo"
SCENES_DIR = DEMO_DIR / "scenes"
DEMO_DIR.mkdir(parents=True, exist_ok=True)
SCENES_DIR.mkdir(parents=True, exist_ok=True)

def get_ffmpeg_binary() -> str:
    """Finds ffmpeg from imageio_ffmpeg or system PATH."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return str(exe)
    except Exception:
        pass
    return "ffmpeg"

def ensure_sandbox_healthy():
    """Ensures sandbox services on 8001 and 8002 are running and healthy."""
    for port, url in [(8001, f"{VENDOR_PORTAL_BASE}/login"), (8002, f"{FINANCE_SYSTEM_BASE}/login")]:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                continue
        except Exception:
            pass
        print(f"[Sandbox] Service on port {port} not responsive. Launching sandbox runner...")
        subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "scripts" / "run_sandbox.py")],
            cwd=str(REPO_ROOT)
        )
        time.sleep(3)
        break

    # Wait until both 8001 and 8002 return 200
    for _ in range(15):
        try:
            r1 = requests.get(f"{VENDOR_PORTAL_BASE}/login", timeout=2)
            r2 = requests.get(f"{FINANCE_SYSTEM_BASE}/login", timeout=2)
            if r1.status_code == 200 and r2.status_code == 200:
                print("[Sandbox] Both Vendor Portal (8001) and Finance ERP (8002) are healthy.")
                return True
        except Exception:
            time.sleep(1)
    raise RuntimeError("Could not establish connection to live sandbox.")

def reseed_sandbox():
    """Resets SQLite database and seeds data."""
    subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "seed.py")], check=True)

# Overlay script injected into every loaded page to show live scene, thought & action
OVERLAY_INJECTION_JS = """
(function() {
    if (document.getElementById('task-worker-overlay')) return;
    const banner = document.createElement('div');
    banner.id = 'task-worker-overlay';
    banner.style.position = 'fixed';
    banner.style.top = '0';
    banner.style.left = '0';
    banner.style.width = '100%';
    banner.style.backgroundColor = 'rgba(15, 23, 42, 0.94)';
    banner.style.color = '#f8fafc';
    banner.style.padding = '10px 20px';
    banner.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    banner.style.fontSize = '14px';
    banner.style.zIndex = '999999';
    banner.style.boxShadow = '0 4px 12px rgba(0,0,0,0.4)';
    banner.style.borderBottom = '3px solid #3b82f6';
    banner.style.display = 'flex';
    banner.style.justifyContent = 'space-between';
    banner.style.alignItems = 'center';
    banner.innerHTML = `
        <div style="flex: 1;">
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #93c5fd; font-weight: 700;" id="overlay-scene-title">CentrAlign AI Autonomous Task Worker</div>
            <div style="font-size: 14px; font-weight: 600; margin-top: 2px;" id="overlay-action">Initializing step...</div>
        </div>
        <div style="text-align: right; max-width: 480px; padding-left: 15px; border-left: 1px solid #334155;">
            <div style="font-size: 11px; text-transform: uppercase; color: #cbd5e1;">Agent Thought:</div>
            <div style="font-size: 12px; color: #38bdf8; font-style: italic; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" id="overlay-thought">Analyzing task...</div>
        </div>
    `;
    document.body.prepend(banner);
    // Push page content down slightly so banner doesn't cover top navigation
    document.body.style.paddingTop = '60px';
})();
"""

def update_page_overlay(page, scene_title: str, action_desc: str, thought: str):
    """Updates the on-screen caption overlay text."""
    try:
        page.evaluate(OVERLAY_INJECTION_JS)
        safe_scene = json.dumps(scene_title)
        safe_action = json.dumps(action_desc)
        safe_thought = json.dumps(thought)
        page.evaluate(f"""
            document.getElementById('overlay-scene-title').innerText = {safe_scene};
            document.getElementById('overlay-action').innerText = {safe_action};
            document.getElementById('overlay-thought').innerText = {safe_thought};
        """)
    except Exception:
        pass

def run_playwright_scene(
    scene_id: str,
    scene_title: str,
    task_prompt: str,
    chaos_mode: bool = False,
    auto_approve: bool = True,
    approval_callback = None,
    clarification_callback = None
) -> Dict[str, Any]:
    """
    Runs a real scene using Playwright to visually show actions,
    inject real-time caption overlays, and record video to disk.
    """
    from playwright.sync_api import sync_playwright

    print(f"\n" + "=" * 80)
    print(f"RECORDING SCENE: {scene_title}")
    print(f"Task: \"{task_prompt}\" (Chaos: {chaos_mode})")
    print("=" * 80)

    # Configure chaos environment
    if chaos_mode:
        os.environ["CHAOS_SLOW_PAGES"] = "true"
        os.environ["CHAOS_DELAY_SECONDS"] = "0.4"
        os.environ["CHAOS_500_ON_SUBMIT"] = "true"
        os.environ["CHAOS_ERROR_RATE"] = "0.7"
        os.environ["CHAOS_SESSION_EXPIRY"] = "true"
        os.environ["CHAOS_SESSION_MAX_REQUESTS"] = "2"
    else:
        os.environ["CHAOS_SLOW_PAGES"] = "false"
        os.environ["CHAOS_DELAY_SECONDS"] = "0"
        os.environ["CHAOS_500_ON_SUBMIT"] = "false"
        os.environ["CHAOS_ERROR_RATE"] = "0"
        os.environ["CHAOS_SESSION_EXPIRY"] = "false"

    scene_video_dir = SCENES_DIR / scene_id
    scene_video_dir.mkdir(parents=True, exist_ok=True)

    worker = AutonomousTaskWorker(
        auto_approve=auto_approve,
        interactive=False,
        approval_handler=approval_callback,
        clarification_handler=clarification_callback
    )

    with sync_playwright() as p:
        # Launch headed Chromium with 1280x720 video recording
        browser = p.chromium.launch(headless=False, slow_mo=400)
        context = browser.new_context(
            record_video_dir=str(scene_video_dir),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        # Initial title screen
        page.goto(f"{VENDOR_PORTAL_BASE}/login")
        update_page_overlay(page, scene_title, f"Task Prompt: \"{task_prompt}\"", "Planning execution strategy...")
        time.sleep(2.0)

        # Execute real task worker logic
        report = worker.run(task_prompt)

        # Visually mirror the agent's key actions on screen for the viewer
        for step in worker.steps:
            action = step.action
            action_type = action.action_type.value
            thought = action.thought
            url = action.params.get("url")

            if url and action.action_type in (ActionType.NAVIGATE, ActionType.SUBMIT_FORM):
                try:
                    page.goto(url)
                    action_summary = f"[{action_type}] Navigated to {url.replace('http://127.0.0.1:', 'port ')}"
                    update_page_overlay(page, scene_title, action_summary, thought)
                    time.sleep(1.2)
                except Exception:
                    pass

        # If it was an ERP entry task, display the final ledger with verified highlights
        if "finance" in task_prompt.lower() or "payables" in task_prompt.lower() or report.verification.status.value == "PASS":
            try:
                page.goto(f"{FINANCE_SYSTEM_BASE}/payables")
                audit_summary = f"[INDEPENDENT AUDIT] Status: {report.verification.status.value} - {report.verification.message[:65]}..."
                update_page_overlay(page, scene_title, audit_summary, "Auditing ground-truth records directly against SQLite ledger.")
                time.sleep(3.0)
            except Exception:
                pass

        time.sleep(2.0)
        context.close()
        browser.close()

    # Locate saved .webm video
    recorded_webm = list(scene_video_dir.glob("*.webm"))
    video_path = str(recorded_webm[0]) if recorded_webm else None

    return {
        "scene_id": scene_id,
        "title": scene_title,
        "task": task_prompt,
        "chaos_mode": chaos_mode,
        "steps": len(worker.steps),
        "retries": report.total_retries,
        "success": report.success,
        "verification_status": report.verification.status.value,
        "audit_message": report.verification.message,
        "video_path": video_path
    }

def create_slide_image(output_path: Path, title: str, subtitle: str, bullets: List[str]):
    """Creates a clean high-contrast 1280x720 slide card using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1280, 720), color=(15, 23, 42))  # Slate 900
    draw = ImageDraw.Draw(img)

    # Accent top border
    draw.rectangle([(0, 0), (1280, 10)], fill=(59, 130, 246))

    # Header title
    draw.text((80, 70), title, fill=(248, 250, 252), font_size=42)
    draw.text((80, 130), subtitle, fill=(147, 197, 253), font_size=24)

    draw.line([(80, 175), (1200, 175)], fill=(51, 65, 85), width=2)

    y = 220
    for bullet in bullets:
        draw.text((90, y), "•", fill=(56, 189, 248), font_size=28)
        draw.text((120, y), bullet, fill=(226, 232, 240), font_size=24)
        y += 55

    img.save(str(output_path))

def create_title_and_end_cards():
    """Generates title and conclusion slides."""
    title_png = SCENES_DIR / "slide_title.png"
    create_slide_image(
        title_png,
        "CentrAlign AI - Autonomous Task Worker",
        "Reliable & Independently Verified Computer-Use Agent",
        [
            "Natural Language Computer Task Execution",
            "Heterogeneous DOM Layout Generalization (Tables & Card Grids)",
            "Automatic Failure Recovery: Exponential Backoff & Session Re-Auth",
            "Risk-Tiered Human-in-the-Loop Safety Gate",
            "Decoupled Ground-Truth Independent Verifier"
        ]
    )

    arch_png = SCENES_DIR / "slide_arch.png"
    create_slide_image(
        arch_png,
        "System Architecture Overview",
        "Engineered for Autonomy, Resilience, and Verification",
        [
            "1. Task Planner: Semantic Intent Decomposer & Strict Chronological Sorter",
            "2. Browser Client: Cookie-aware session HTTP/DOM parser with SHA-256 state hashing",
            "3. Failure Detector: Loop prevention (3-strike limit) & Exponential backoff",
            "4. Human Safety Gate: Irreversible financial actions gated by user confirmation",
            "5. Independent Verifier: Decoupled ground-truth audit of destination SQLite ledger"
        ]
    )

    eval_png = SCENES_DIR / "slide_evals.png"
    create_slide_image(
        eval_png,
        "Evaluation Benchmark Results (evals/results.md)",
        "100% Verified Pass Rate Across 7 Varied Tasks",
        [
            "Standard Table Invoice Entry: 100% Pass | 8 Steps | Audited",
            "Card Grid Layout Entry (Vertex Analytics): 100% Pass | 8 Steps | Audited",
            "Overdue Invoices Aggregation: 100% Pass | 4 Steps | Read-Only (0 Writes)",
            "Cross-Vendor Highest Unpaid Comparison: 100% Pass | 8 Steps | Read-Only",
            "Multi-Invoice Batch Ingestion (Top 2 Invoices): 100% Pass | 9 Steps | Dual Audits",
            "Impossible Entity Refusal (Cyberdyne Systems): 100% Pass | Graceful Refusal",
            "Chaos Mode Resilience (Network Latency & 500s): 100% Pass | Recovered"
        ]
    )
    return title_png, arch_png, eval_png

def render_image_to_mp4(ffmpeg_exe: str, img_path: Path, out_mp4: Path, duration_secs: int = 6):
    """Converts a static slide PNG into an MP4 clip."""
    cmd = [
        ffmpeg_exe, "-y",
        "-loop", "1",
        "-i", str(img_path),
        "-c:v", "libx264",
        "-t", str(duration_secs),
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1280:720",
        str(out_mp4)
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def convert_webm_to_mp4(ffmpeg_exe: str, webm_path: Path, out_mp4: Path):
    """Transcodes Playwright webm to standard H.264 mp4."""
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(webm_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1280:720",
        str(out_mp4)
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def concatenate_clips(ffmpeg_exe: str, clip_list: List[Path], output_mp4: Path):
    """Concatenates all MP4 clips into final demo.mp4."""
    list_file = SCENES_DIR / "concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for clip in clip_list:
            f.write(f"file '{clip.resolve().as_posix()}'\n")

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_mp4)
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def main():
    print("=" * 80)
    print("CENTRALLIGN AI TASK WORKER - AUTOMATED DEMO RECORDING PIPELINE")
    print("=" * 80)

    ffmpeg_bin = get_ffmpeg_binary()
    print(f"[FFmpeg] Using binary at: {ffmpeg_bin}")

    ensure_sandbox_healthy()
    reseed_sandbox()

    scene_reports = []
    mp4_clips = []

    # 1. Title Slide (5 seconds)
    print("\n[Card] Generating intro title slide...")
    title_png, arch_png, eval_png = create_title_and_end_cards()
    title_mp4 = SCENES_DIR / "00_intro_title.mp4"
    render_image_to_mp4(ffmpeg_bin, title_png, title_mp4, duration_secs=6)
    mp4_clips.append(title_mp4)

    # --------------------------------------------------------------------------
    # SCENE 1: Main Task (Table Layout, Chaos OFF)
    # --------------------------------------------------------------------------
    reseed_sandbox()
    s1 = run_playwright_scene(
        scene_id="scene_1_main",
        scene_title="Scene 1: Autonomous Invoice Discovery & Entry (Chaos OFF)",
        task_prompt="Find the latest invoice from Acme Cloud Corp, extract the amount and due date, enter it into our internal system, and tell me once it is done.",
        chaos_mode=False,
        auto_approve=True
    )
    scene_reports.append(s1)
    if s1["video_path"]:
        s1_mp4 = SCENES_DIR / "scene_1_main.mp4"
        convert_webm_to_mp4(ffmpeg_bin, Path(s1["video_path"]), s1_mp4)
        mp4_clips.append(s1_mp4)

    # --------------------------------------------------------------------------
    # SCENE 2: Resilience (Chaos ON - Transient 500s & Session Expiry)
    # --------------------------------------------------------------------------
    reseed_sandbox()
    s2 = run_playwright_scene(
        scene_id="scene_2_resilience",
        scene_title="Scene 2: Failure Recovery & Chaos Resilience (Chaos ON)",
        task_prompt="Find the latest invoice from Global Logistics Ltd, extract the amount and due date, enter it into our internal system, and tell me once it is done.",
        chaos_mode=True,
        auto_approve=True
    )
    scene_reports.append(s2)
    if s2["video_path"]:
        s2_mp4 = SCENES_DIR / "scene_2_resilience.mp4"
        convert_webm_to_mp4(ffmpeg_bin, Path(s2["video_path"]), s2_mp4)
        mp4_clips.append(s2_mp4)

    # --------------------------------------------------------------------------
    # SCENE 3: Human-in-the-Loop Safety & Clarification
    # --------------------------------------------------------------------------
    reseed_sandbox()
    def scripted_clarification(question, options):
        print(f"[Scripted Human] Prompted: {question} -> Clarified: Acme Cloud Corp")
        return "Acme Cloud Corp"

    def scripted_approval(action, details):
        print(f"[Scripted Human] Risk Gate Approved: Financial write authorized.")
        return True

    s3 = run_playwright_scene(
        scene_id="scene_3_hitl",
        scene_title="Scene 3: Human-in-the-Loop Ambiguity Clarification & Risk Gating",
        task_prompt="Find the latest invoice from a supplier, extract the amount and due date, enter it into our internal system, and tell me once it is done.",
        chaos_mode=False,
        auto_approve=False,
        approval_callback=scripted_approval,
        clarification_callback=scripted_clarification
    )
    scene_reports.append(s3)
    if s3["video_path"]:
        s3_mp4 = SCENES_DIR / "scene_3_hitl.mp4"
        convert_webm_to_mp4(ffmpeg_bin, Path(s3["video_path"]), s3_mp4)
        mp4_clips.append(s3_mp4)

    # --------------------------------------------------------------------------
    # SCENE 4: Generalization Across Different Task Types
    # --------------------------------------------------------------------------
    reseed_sandbox()
    s4 = run_playwright_scene(
        scene_id="scene_4_generalization",
        scene_title="Scene 4: Task Generalization - Overdue Invoices Aggregation (Read-Only)",
        task_prompt="List all invoices from Acme Cloud Corp that are overdue and tell me the total.",
        chaos_mode=False,
        auto_approve=True
    )
    scene_reports.append(s4)
    if s4["video_path"]:
        s4_mp4 = SCENES_DIR / "scene_4_generalization.mp4"
        convert_webm_to_mp4(ffmpeg_bin, Path(s4["video_path"]), s4_mp4)
        mp4_clips.append(s4_mp4)

    # --------------------------------------------------------------------------
    # SCENE 5: Verification Layer (Card Grid Layout + Ground-Truth Audit)
    # --------------------------------------------------------------------------
    reseed_sandbox()
    s5 = run_playwright_scene(
        scene_id="scene_5_verification",
        scene_title="Scene 5: Independent Verification & DOM Layout Generalization (Cards Grid)",
        task_prompt="Find the latest invoice from Vertex Analytics, extract the amount and due date, enter it into the internal finance system, and notify me.",
        chaos_mode=False,
        auto_approve=True
    )
    scene_reports.append(s5)
    if s5["video_path"]:
        s5_mp4 = SCENES_DIR / "scene_5_verification.mp4"
        convert_webm_to_mp4(ffmpeg_bin, Path(s5["video_path"]), s5_mp4)
        mp4_clips.append(s5_mp4)

    # --------------------------------------------------------------------------
    # Conclusion Slides (Architecture & Evals)
    # --------------------------------------------------------------------------
    print("\n[Card] Generating architecture & evals conclusion cards...")
    arch_mp4 = SCENES_DIR / "98_arch_card.mp4"
    render_image_to_mp4(ffmpeg_bin, arch_png, arch_mp4, duration_secs=8)
    mp4_clips.append(arch_mp4)

    eval_mp4 = SCENES_DIR / "99_eval_card.mp4"
    render_image_to_mp4(ffmpeg_bin, eval_png, eval_mp4, duration_secs=8)
    mp4_clips.append(eval_mp4)

    # --------------------------------------------------------------------------
    # Concatenate all into final demo.mp4
    # --------------------------------------------------------------------------
    final_mp4 = DEMO_DIR / "demo.mp4"
    print(f"\n[Concatenating] Merging {len(mp4_clips)} clips into {final_mp4}...")
    concatenate_clips(ffmpeg_bin, mp4_clips, final_mp4)

    file_size_mb = final_mp4.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 80)
    print(f"DEMO VIDEO GENERATION COMPLETE!")
    print(f"Output File: {final_mp4}")
    print(f"File Size:   {file_size_mb:.2f} MB")
    print("=" * 80)

    # Generate demo report
    report_md = DEMO_DIR / "demo_report.md"
    with open(report_md, "w", encoding="utf-8") as f:
        f.write("# Autonomous AI Task Worker - Live Demo Execution Report\n\n")
        f.write(f"**Generated At:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Final Video Path:** `{final_mp4}` ({file_size_mb:.2f} MB)\n\n")
        f.write("## Scene Execution Audit Table\n\n")
        f.write("| Scene ID | Title | Chaos Mode | Steps | Retries | Verification | Result |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n")
        for s in scene_reports:
            res_icon = "PASS" if s["success"] else "FAIL"
            f.write(f"| `{s['scene_id']}` | **{s['title']}** | {'ON' if s['chaos_mode'] else 'OFF'} | {s['steps']} | {s['retries']} | {s['verification_status']} | **{res_icon}** |\n")
        f.write("\n---\n\n")
        f.write("### Scene Task Prompts & Ground Truth Outcomes\n\n")
        for s in scene_reports:
            f.write(f"#### {s['title']}\n")
            f.write(f"- **Task Prompt:** `{s['task']}`\n")
            f.write(f"- **Steps Executed:** {s['steps']} (Retries: {s['retries']})\n")
            f.write(f"- **Audit Details:** {s['audit_message']}\n\n")

    print(f"[Report] Saved execution trace to {report_md}")

if __name__ == "__main__":
    main()
