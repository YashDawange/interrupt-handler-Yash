# interrupt_handler.py
# Author: ABHAY KUMAR
# Description: Logic layer for Intelligent Interruption Handling
# Used in: examples/voice_agents/intelligent_interrupt_agent.py

from dataclasses import dataclass
from typing import Iterable


@dataclass
class InterruptConfig:
    """
    Stores lists of:
      - soft backchannel words (IGNORE while agent speaking)
      - strong command words (INTERRUPT immediately)
    """

    ignore_words: set[str]
    command_words: set[str]

    @classmethod
    def default(cls) -> "InterruptConfig":
        return cls(
            ignore_words={
                "yeah", "ya", "yup", "ok", "okay", "k",
                "hmm", "hmmm", "uh huh", "uh-huh",
                "right", "mm", "mhm", "aha","oohhh","ohh","nice"
            },
            command_words={
                "stop", "wait", "no", "pause",
                "hold on", "hang on",
                "one second", "wait a second",
                "wait a minute","stop right now"," i have a doubt"
            },
        )


class InterruptHandler:
    """
    Classifies user input based on spoken text.

    Returns:
      - "IGNORE"    → Soft filler input (yeah, ok, hmm)
      - "INTERRUPT" → Contains any command (stop, wait, no)
      - "NORMAL"    → Any other input
    """

    def __init__(self, config: InterruptConfig | None = None):
        self.config = config or InterruptConfig.default()

    # internal helpers

    def _normalize(self, text: str) -> str:
        """Lowercase + clean multiple spaces."""
        return " ".join(text.lower().strip().split())

    def _contains_any(self, text: str, words: Iterable[str]) -> bool:
        """Check if any word/phrase appears in the text."""
        return any(w in text for w in words)

    #  main classification 
    def classify(self, text: str) -> str:
        """
        Main API called by the agent.

        Example:
            text = "yeah ok"
            return "IGNORE"

            text = "yeah wait"
            return "INTERRUPT"

            text = "tell me something"
            return "NORMAL"
        """
        if not text:
            return "NORMAL"

        norm = self._normalize(text)

        # 1️ Mixed input containing command → highest priority
        if self._contains_any(norm, self.config.command_words):
            return "INTERRUPT"

        # 2️ Pure soft backchannel
        if norm in self.config.ignore_words:
            return "IGNORE"

        # 3️ “ok ok ok” or “yeah yeah” repeated fillers
        tokens = norm.split()
        if all(tok in self.config.ignore_words for tok in tokens):
            return "IGNORE"

        return "NORMAL"
