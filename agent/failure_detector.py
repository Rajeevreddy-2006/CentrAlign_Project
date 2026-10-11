import json
import time
from typing import List, Tuple, Dict, Any, Optional
from agent.models import Action, ActionResult, ActionType
from agent.config import MAX_RETRIES_PER_STEP, EXPONENTIAL_BACKOFF_BASE, MAX_LOOP_COUNT

class LoopDetectedError(Exception):
    """Raised when the agent attempts the exact same action 3 times consecutively."""
    pass

class FailureManager:
    """
    Monitors execution stream to detect:
    1. Tool exceptions & timeouts
    2. HTTP errors & DOM error banners
    3. Action loops (identical action executed 3 times)
    4. Stagnant progress (no DOM state transition following write action)
    5. Mid-task session expiration
    """
    def __init__(self):
        self.action_history: List[Tuple[ActionType, str]] = []
        self.state_hashes: List[str] = []
        self.remediated_failures: List[str] = []

    def record_action(self, action: Action):
        """Records action signature for loop detection."""
        key = (action.action_type, json.dumps(action.params, sort_keys=True))
        self.action_history.append(key)

    def is_loop_detected(self, action: Action) -> bool:
        """
        Checks if the current action has already been attempted MAX_LOOP_COUNT times
        with identical arguments consecutively.
        """
        key = (action.action_type, json.dumps(action.params, sort_keys=True))
        if len(self.action_history) < MAX_LOOP_COUNT:
            return False

        recent = self.action_history[-MAX_LOOP_COUNT:]
        return all(item == key for item in recent)

    def check_stagnant_progress(self, action: Action, result: ActionResult) -> bool:
        """
        Detects if a state-modifying action caused no DOM state transition.
        """
        if action.action_type in (ActionType.SUBMIT_FORM, ActionType.LOGIN):
            if result.state_hash and self.state_hashes:
                if result.state_hash == self.state_hashes[-1] and not result.success:
                    return True
        if result.state_hash:
            self.state_hashes.append(result.state_hash)
        return False

    def is_session_expired(self, result: ActionResult) -> bool:
        """
        Detects whether an action triggered a session timeout requiring re-login.
        """
        if result.data and result.data.get("is_session_expired"):
            return True
        if result.current_url and "/login" in result.current_url.lower():
            if result.action_type not in (ActionType.LOGIN, ActionType.NAVIGATE):
                return True
        if result.error and "session expired" in result.error.lower():
            return True
        return False

    def should_retry_transient(self, result: ActionResult, retry_count: int) -> bool:
        """
        Determines if a failed result is transient (e.g. 500 error or network timeout)
        and still within the retry limit.
        """
        if retry_count >= MAX_RETRIES_PER_STEP:
            return False
        return result.is_transient

    def compute_backoff(self, retry_count: int) -> float:
        """Calculates exponential backoff delay."""
        return EXPONENTIAL_BACKOFF_BASE * (2 ** retry_count)

    def record_remediation(self, note: str):
        """Logs successful recovery from a failure."""
        self.remediated_failures.append(note)
