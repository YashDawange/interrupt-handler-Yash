from __future__ import annotations
import os
import re

from agent_types import UserInputType


class InputClassifier:
    """Classifies user text into backchannel, command, or query."""

    BACKCHANNEL_PATTERNS = [
        r"^yeah\.?\s*$",
        r"^yep\.?\s*$",
        r"^ok(ay)?\.?\s*$",
        r"^hmm+\.?\s*$",
        r"^uh\s*-?huh\.?\s*$",
        r"^mhm+\.?\s*$",
        r"^right\.?\s*$",
        r"^aha+\.?\s*$",
        r"^sure\.?\s*$",
        r"^alright\.?\s*$",
        r"^got\s+it\.?\s*$",
        r"^continue\.?\s*$",
    ]

    @staticmethod
    def _load_backchannel_words() -> set[str]:
        """Load backchannel keywords from env or defaults."""
        env_words = os.getenv("BACKCHANNEL_WORDS", "")
        if env_words.strip():
            return {w.strip().lower() for w in env_words.split(",") if w.strip()}
        return {
            "yeah", "yep", "ok", "okay", "hmm", "mm", "uh", "uhh", "uh-huh",
            "right", "alright", "aha", "got", "it", "sure", "mhm", "yup", "ooh",
        }

    @staticmethod
    def _load_command_words() -> set[str]:
        """Load command keywords from env or defaults."""
        env_words = os.getenv("COMMAND_WORDS", "")
        if env_words.strip():
            return {w.strip().lower() for w in env_words.split(",") if w.strip()}
        return {
            "wait", "stop", "no", "cancel", "pause", "hold", "nevermind",
            "never", "mind", "whoa", "shut", "quiet", "enough",
        }

    def __init__(self):
        """Initialize classifier with loaded keywords and regex patterns."""
        self._backchannel_words = self._load_backchannel_words()
        self._cmd_words = self._load_command_words()
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.BACKCHANNEL_PATTERNS]

    def categorize_input(self, text: str) -> UserInputType:
        """Return the type of user input based on patterns and keywords."""
        if not text or not text.strip():
            return UserInputType.BACKCHANNEL

        normalized = text.strip().lower()

        if any(p.match(normalized) for p in self._compiled_patterns):
            return UserInputType.BACKCHANNEL

        tokens = set(re.sub(r"[.,!?;:\-]", " ", normalized).split())

        if any(cmd in tokens for cmd in self._cmd_words):
            return UserInputType.COMMAND

        if tokens and all(t in self._backchannel_words for t in tokens):
            return UserInputType.BACKCHANNEL

        return UserInputType.QUERY
