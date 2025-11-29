"""Configuration for intelligent interruption handling.

This module provides configuration classes for the smart interruption filter
that allows agents to ignore backchannel words (e.g., "yeah", "ok", "hmm")
when speaking while still responding to genuine interruptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["InterruptionConfig", "DEFAULT_BACKCHANNEL_WORDS", "DEFAULT_INTERRUPT_KEYWORDS"]


# Default set of backchannel words that indicate passive listening
DEFAULT_BACKCHANNEL_WORDS = frozenset(
    {
        "yeah",
        "ok",
        "okay",
        "hmm",
        "uh-huh",
        "uh huh",
        "right",
        "aha",
        "mhm",
        "mm-hmm",
        "mm hmm",
        "sure",
        "got it",
        "yep",
        "yup",
        "uh",
        "mm",
        "mhmm",
        "uh-huh",
        "yes",
        "alright",
        "cool",
        "k",
    }
)

# Default set of interrupt keywords that indicate genuine interruptions
DEFAULT_INTERRUPT_KEYWORDS = frozenset(
    {
        "wait",
        "stop",
        "no",
        "hold on",
        "pause",
        "hold",
        "hang on",
        "actually",
        "but",
        "hold up",
        "excuse me",
        "sorry",
        "pardon",
    }
)


@dataclass
class InterruptionConfig:
    """Configuration for the smart interruption filter.

    Attributes:
        backchannel_words: Set of words that are considered passive acknowledgments.
            When the agent is speaking and the user says only these words, the agent
            will continue speaking without interruption.
        interrupt_keywords: Set of keywords that indicate a genuine interruption.
            If any of these words appear in user speech while the agent is speaking,
            the agent will stop immediately.
        stt_timeout: Maximum time (in seconds) to wait for STT transcription before
            treating the speech as a genuine interruption. Default is 0.5 seconds.
        case_sensitive: Whether word matching should be case-sensitive. Default is False.
        min_words_for_interrupt: Minimum number of words required to trigger an
            interruption when not all words are backchannels. Default is 1.
    """

    backchannel_words: set[str] = field(
        default_factory=lambda: set(DEFAULT_BACKCHANNEL_WORDS)
    )
    interrupt_keywords: set[str] = field(
        default_factory=lambda: set(DEFAULT_INTERRUPT_KEYWORDS)
    )
    stt_timeout: float = 0.5
    case_sensitive: bool = False
    min_words_for_interrupt: int = 1

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.stt_timeout <= 0:
            raise ValueError("stt_timeout must be positive")
        if self.min_words_for_interrupt < 1:
            raise ValueError("min_words_for_interrupt must be at least 1")

        # Normalize words to lowercase if not case-sensitive
        if not self.case_sensitive:
            self.backchannel_words = {word.lower() for word in self.backchannel_words}
            self.interrupt_keywords = {word.lower() for word in self.interrupt_keywords}
