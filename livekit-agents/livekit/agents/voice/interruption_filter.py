from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_session import AgentSession


@dataclass
class InterruptionFilterConfig:
    """Configuration for the intelligent interruption filter."""

    passive_words: list[str] = field(
        default_factory=lambda: [
            "yeah",
            "yea",
            "yes",
            "yep",
            "yup",
            "ok",
            "okay",
            "hmm",
            "hm",
            "mm",
            "mhm",
            "mmhmm",
            "mm-hmm",
            "uh-huh",
            "uh huh",
            "uhuh",
            "right",
            "aha",
            "ah",
            "oh",
            "sure",
            "got it",
            "i see",
            "alright",
            "all right",
        ]
    )
    """Words/phrases that indicate passive acknowledgement (backchanneling)."""

    interrupt_words: list[str] = field(
        default_factory=lambda: [
            "wait",
            "stop",
            "no",
            "hold on",
            "hold up",
            "pause",
            "hang on",
            "one moment",
            "one second",
            "actually",
            "but",
            "however",
            "excuse me",
            "sorry",
            "question",
            "can i",
            "let me",
            "i have",
            "what about",
            "how about",
        ]
    )
    """Words/phrases that indicate an active interruption request."""

    enabled: bool = True
    """Whether the interruption filter is enabled."""

    @classmethod
    def from_env(cls) -> InterruptionFilterConfig:
        """Create config from environment variables."""
        config = cls()

        if os.environ.get("LIVEKIT_INTERRUPTION_FILTER_ENABLED", "").lower() == "false":
            config.enabled = False

        passive_words_env = os.environ.get("LIVEKIT_PASSIVE_WORDS")
        if passive_words_env:
            config.passive_words = [w.strip().lower() for w in passive_words_env.split(",")]

        interrupt_words_env = os.environ.get("LIVEKIT_INTERRUPT_WORDS")
        if interrupt_words_env:
            config.interrupt_words = [w.strip().lower() for w in interrupt_words_env.split(",")]

        return config


class InterruptionFilter:
    """
    Context-aware interruption filter for voice agents.

    This filter distinguishes between:
    1. Passive acknowledgements ("yeah", "ok", "hmm") - should be ignored when agent is speaking
    2. Active interruptions ("wait", "stop", "no") - should always interrupt the agent
    3. Valid input when agent is silent - should be processed normally
    """

    def __init__(self, config: InterruptionFilterConfig | None = None) -> None:
        self._config = config or InterruptionFilterConfig()
        self._passive_pattern = self._build_pattern(self._config.passive_words)
        self._interrupt_pattern = self._build_pattern(self._config.interrupt_words)

    @property
    def config(self) -> InterruptionFilterConfig:
        return self._config

    def _build_pattern(self, words: list[str]) -> re.Pattern[str]:
        """Build a regex pattern from a list of words/phrases."""
        escaped = [re.escape(w) for w in sorted(words, key=len, reverse=True)]
        pattern = r"\b(" + "|".join(escaped) + r")\b"
        return re.compile(pattern, re.IGNORECASE)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _is_only_passive(self, text: str) -> bool:
        """Check if the text contains only passive acknowledgement words."""
        normalized = self._normalize_text(text)
        if not normalized:
            return True

        remaining = self._passive_pattern.sub("", normalized).strip()
        remaining = re.sub(r"\s+", " ", remaining).strip()

        return len(remaining) == 0

    def _contains_interrupt_command(self, text: str) -> bool:
        """Check if the text contains any interrupt command words."""
        normalized = self._normalize_text(text)
        return bool(self._interrupt_pattern.search(normalized))

    def should_interrupt(self, transcript: str, agent_is_speaking: bool) -> bool:
        """
        Determine if the given transcript should trigger an interruption.

        Args:
            transcript: The user's speech transcript
            agent_is_speaking: Whether the agent is currently speaking

        Returns:
            True if the agent should be interrupted, False otherwise

        Logic:
        - If agent is silent: Always allow (return True)
        - If agent is speaking:
            - If transcript contains interrupt commands: Interrupt (return True)
            - If transcript is only passive words: Don't interrupt (return False)
            - Otherwise: Interrupt (return True)
        """
        if not self._config.enabled:
            return True

        transcript = transcript.strip()
        if not transcript:
            return False

        if not agent_is_speaking:
            return True

        if self._contains_interrupt_command(transcript):
            return True

        if self._is_only_passive(transcript):
            return False

        return True

    def get_filter_reason(self, transcript: str, agent_is_speaking: bool) -> str:
        """Get a human-readable reason for the filter decision (for debugging)."""
        if not self._config.enabled:
            return "filter_disabled"

        if not transcript.strip():
            return "empty_transcript"

        if not agent_is_speaking:
            return "agent_silent"

        if self._contains_interrupt_command(transcript):
            return "contains_interrupt_command"

        if self._is_only_passive(transcript):
            return "passive_acknowledgement"

        return "valid_input"


_default_filter: InterruptionFilter | None = None


def get_default_interruption_filter() -> InterruptionFilter:
    """Get the default global interruption filter instance."""
    global _default_filter
    if _default_filter is None:
        _default_filter = InterruptionFilter(InterruptionFilterConfig.from_env())
    return _default_filter


def set_default_interruption_filter(filter: InterruptionFilter) -> None:
    """Set the default global interruption filter instance."""
    global _default_filter
    _default_filter = filter
