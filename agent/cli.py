#!/usr/bin/env python3
"""
CLI Entrypoint for the CentrAlign Autonomous AI Task Worker.
Usage:
  python -m agent.cli --task "Find the latest invoice from Acme Cloud Corp..." [--auto-approve]
"""

import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.runner import AutonomousTaskWorker

def main():
    parser = argparse.ArgumentParser(
        description="CentrAlign Autonomous AI Task Worker - Reliable & Independently Verified Computer Use Agent"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="Find the latest invoice from Acme Cloud Corp, extract the amount and due date, enter it into our internal system, and tell me once it is done.",
        help="Natural language instruction for the autonomous task worker."
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Bypass interactive human approval gate for irreversible/financial write operations."
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without waiting for interactive terminal input."
    )

    args = parser.parse_args()

    worker = AutonomousTaskWorker(
        auto_approve=args.auto_approve,
        interactive=not args.non_interactive
    )

    try:
        report = worker.run(args.task)
        print("\n" + "=" * 70)
        print("  FINAL WORKER SUMMARY")
        print("=" * 70)
        print(f"Outcome:              {'SUCCESS (VERIFIED)' if report.success else 'FAILED / UNVERIFIED'}")
        print(f"Verification Status:  {report.verification.status.value}")
        print(f"Claimed Summary:      {report.claimed_summary}")
        print(f"Audit Message:        {report.verification.message}")
        print(f"Artifacts:            {report.evidence_files}")
        print("=" * 70)
        sys.exit(0 if report.success else 1)
    except Exception as e:
        print(f"\n[FATAL ERROR] Execution Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
