from __future__ import annotations

from settings import InterruptionSettings
from logger import EventLogger
from agent_types import UserInputType


class ConversationAnalyzer:
    """Analyzes user input to decide how the agent should handle interruptions."""

    def __init__(self, config: InterruptionSettings, logger: EventLogger):
        """Initialize analyzer with interruption settings and event logger."""
        self._config = config
        self._logger = logger

    def determine_handling_strategy(
        self,
        utterance: str,
        classification: UserInputType,
        agent_is_speaking: bool,
        is_final: bool,
    ) -> str:
        """Return handling strategy based on user input type and conversation state."""
        if agent_is_speaking:
            if classification == UserInputType.BACKCHANNEL:
                self._logger.capture_handling_decision("IGNORE", "Backchannel while agent speaking")
                return "IGNORE"

            if classification == UserInputType.COMMAND:
                self._logger.capture_handling_decision("INTERRUPT", "Hard command detected while speaking")
                return "INTERRUPT"

            if not is_final:
                self._logger.capture_handling_decision("WAIT", "Meaningful but interim while agent speaking")
                return "WAIT"

            self._logger.capture_handling_decision("INTERRUPT_AND_RESPOND", "Meaningful final while speaking")
            return "INTERRUPT_AND_RESPOND"

        if is_final:
            self._logger.capture_handling_decision("RESPOND", "Agent listening and user is final")
            return "RESPOND"

        self._logger.capture_handling_decision("WAIT", "Agent listening but transcript is interim")
        return "WAIT"
