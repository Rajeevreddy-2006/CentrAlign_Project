import sys
from typing import Optional, List, Callable, Dict, Any
from agent.models import Action, ActionType, RiskLevel

def classify_action_risk(action: Action) -> RiskLevel:
    """
    Classifies an action by its business risk profile.
    - Financial writes (creating payables) are classified as IRREVERSIBLE_FINANCIAL_WRITE.
    - Read actions (navigation, page parsing, downloading PDFs) are classified as READ_ONLY.
    """
    if action.action_type == ActionType.SUBMIT_FORM:
        endpoint = str(action.params.get("url", "")).lower()
        if "payable" in endpoint or "add" in endpoint:
            return RiskLevel.IRREVERSIBLE_FINANCIAL_WRITE
        return RiskLevel.REVERSIBLE_WRITE

    return RiskLevel.READ_ONLY

class HumanApprovalGate:
    """
    Handles human-in-the-loop approvals for dangerous/financial actions
    and clarifies ambiguity with the user.
    """
    def __init__(
        self,
        auto_approve: bool = False,
        interactive: bool = True,
        approval_handler: Optional[Callable[[Action, str], bool]] = None,
        clarification_handler: Optional[Callable[[str, Optional[List[str]]], str]] = None
    ):
        self.auto_approve = auto_approve
        self.interactive = interactive
        self.approval_handler = approval_handler
        self.clarification_handler = clarification_handler

    def request_approval(self, action: Action, details: Dict[str, Any]) -> bool:
        """
        Evaluates whether an action requires human approval.
        Returns True if approved, False if rejected.
        """
        risk = classify_action_risk(action)

        if risk == RiskLevel.READ_ONLY:
            return True

        if self.auto_approve:
            print(f"[Auto-Approve] Bypassing human confirmation for {action.action_type} (auto_approve=True).")
            return True

        if self.approval_handler:
            return self.approval_handler(action, str(details))

        if not self.interactive:
            print(f"[Approval Denied] Non-interactive environment and action is {risk.value}.")
            return False

        # Interactive CLI Prompt
        print("\n" + "=" * 70)
        print("  [HUMAN APPROVAL REQUIRED]: FINANCIAL ACTION DETECTED")
        print("=" * 70)
        print(f"Action Type:  {action.action_type.value}")
        print(f"Risk Level:   {risk.value}")
        print(f"Action Goal:  {action.thought}")
        print("Parameters:")
        for k, v in details.items():
            print(f"  * {k}: {v}")
        print("=" * 70)

        sys.stdout.write("Authorize this financial write into the internal ERP system? (yes/no) [no]: ")
        sys.stdout.flush()
        try:
            choice = input().strip().lower()
            approved = choice in ("y", "yes")
            if approved:
                print("[Approved] Human authorized execution.")
            else:
                print("[Rejected] Human rejected the action.")
            return approved
        except (EOFError, KeyboardInterrupt):
            print("\n[Aborted] Human input aborted.")
            return False

    def request_clarification(self, question: str, options: Optional[List[str]] = None) -> str:
        """
        Asks the user for clarification when task instructions or data are ambiguous.
        """
        if self.clarification_handler:
            return self.clarification_handler(question, options)

        print("\n" + "?" * 70)
        print("  [HUMAN CLARIFICATION REQUIRED] (AMBIGUOUS STATE DETECTED)")
        print("?" * 70)
        print(f"Question: {question}")
        if options:
            print("Options:")
            for idx, opt in enumerate(options, 1):
                print(f"  [{idx}] {opt}")
        print("?" * 70)

        if not self.interactive:
            return options[0] if options else ""

        sys.stdout.write("Please provide clarification or select option number: ")
        sys.stdout.flush()
        try:
            answer = input().strip()
            if options and answer.isdigit():
                choice_idx = int(answer) - 1
                if 0 <= choice_idx < len(options):
                    answer = options[choice_idx]
            return answer
        except (EOFError, KeyboardInterrupt):
            print("\n[Aborted] Clarification aborted.")
            return ""
