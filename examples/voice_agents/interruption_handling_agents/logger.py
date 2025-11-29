from __future__ import annotations
from typing import Optional

from agent_types import UserInputType


class EventLogger:
    """Simple console logger for user input, decisions, actions, and errors."""

    def __init__(self, logger_name: str = "voice-agent-interruption"):
        """Initialize logger with a name."""
        self._logger_name = logger_name

    def capture_user_input(self, utterance: str, is_complete: bool, currently_speaking: bool):
        """Log raw user input along with state info."""
        completion_status = "final" if is_complete else "interim"
        agent_status = "speaking" if currently_speaking else "listening"
        print(f"[INPUT] utterance='{utterance}' status={completion_status} agent={agent_status}")

    def capture_classification(self, utterance: str, classification: UserInputType):
        """Log how the input was classified."""
        print(f"[CLASSIFY] utterance='{utterance}' → {classification.value}")

    def capture_handling_decision(self, decision: str, reasoning: str):
        """Log decision about how the agent handles the input."""
        print(f"[DECIDE] {decision}: {reasoning}")

    def capture_action(self, action: str, details: str = ""):
        """Log an action the agent performs."""
        if details:
            print(f"[EXECUTE] {action} ({details})")
        else:
            print(f"[EXECUTE] {action}")

    def capture_lifecycle_event(self, event: str):
        """Log lifecycle events like start/stop."""
        print(f"[LIFECYCLE] {event}")

    def capture_error(self, msg: str, exc: Optional[Exception] = None):
        """Log errors with optional exception info."""
        if exc:
            print(f"[ERROR] {msg}: {exc}")
        else:
            print(f"[ERROR] {msg}")
