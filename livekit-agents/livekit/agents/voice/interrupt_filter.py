from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable

from ..log import logger


# Default backchanneling words to ignore while agent is speaking
DEFAULT_BACKCHANNELING_WORDS = [
    "yeah",
    "yep",
    "yes",
    "yup",
    "ok",
    "okay",
    "hmm",
    "hm",
    "uh-huh",
    "uh huh",
    "uhuh",
    "mhm",
    "mm-hmm",
    "mm hmm",
    "mmhmm",
    "right",
    "aha",
    "ah",
    "oh",
    "i see",
    "sure",
    "gotcha",
    "got it",
    "alright",
    "all right",
    "fine",
    "cool",
    "nice",
    "great",
    "good",
    "indeed",
    "absolutely",
    "exactly",
    "totally",
    "definitely",
    "certainly",
    "of course",
    "true",
]

# Default interrupt words that should always cause an interruption
DEFAULT_INTERRUPT_WORDS = [
    "stop",
    "wait",
    "hold on",
    "hold up",
    "pause",
    "no",
    "nope",
    "cancel",
    "quiet",
    "shut up",
    "be quiet",
    "silence",
    "enough",
    "halt",
    "hang on",
    "one moment",
    "one second",
    "just a moment",
    "just a second",
    "question",
    "but",
    "however",
    "actually",
    "excuse me",
    "sorry",
    "let me",
    "can i",
    "may i",
    "i have",
    "i need",
    "i want",
]


def _load_words_from_env(env_var: str, default: list[str]) -> list[str]:
    """Load words from environment variable (comma-separated) or use default."""
    env_value = os.environ.get(env_var)
    if env_value:
        return [word.strip().lower() for word in env_value.split(",") if word.strip()]
    return default


def _normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, strip, collapse whitespace)."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    # Remove common punctuation
    text = re.sub(r"[.,!?;:\"']+", "", text)
    return text


def _split_into_words(text: str) -> list[str]:
    """Split text into individual words."""
    return _normalize_text(text).split()


@dataclass
class InterruptFilterConfig:
    """Configuration for the interrupt filter."""

    enabled: bool = True
    """Whether to enable intelligent interruption filtering."""

    backchanneling_words: list[str] = field(
        default_factory=lambda: _load_words_from_env(
            "LIVEKIT_BACKCHANNELING_WORDS", DEFAULT_BACKCHANNELING_WORDS
        )
    )
    """Words to ignore while agent is speaking (backchanneling/acknowledgements)."""

    interrupt_words: list[str] = field(
        default_factory=lambda: _load_words_from_env(
            "LIVEKIT_INTERRUPT_WORDS", DEFAULT_INTERRUPT_WORDS
        )
    )
    """Words that should always trigger an interruption, even if mixed with backchanneling."""

    case_sensitive: bool = False
    """Whether word matching should be case-sensitive."""


class InterruptFilter:


    def __init__(
        self,
        config: InterruptFilterConfig | None = None,
        *,
        enabled: bool | None = None,
        backchanneling_words: list[str] | None = None,
        interrupt_words: list[str] | None = None,
    ) -> None:

        if config is not None:
            self._config = config
        else:
            self._config = InterruptFilterConfig(
                enabled=enabled if enabled is not None else True,
                backchanneling_words=backchanneling_words or DEFAULT_BACKCHANNELING_WORDS.copy(),
                interrupt_words=interrupt_words or DEFAULT_INTERRUPT_WORDS.copy(),
            )

        # Pre-compile normalized word sets for fast lookup
        self._backchanneling_set: set[str] = set()
        self._interrupt_set: set[str] = set()
        self._rebuild_word_sets()

    def _rebuild_word_sets(self) -> None:
        if self._config.case_sensitive:
            self._backchanneling_set = set(self._config.backchanneling_words)
            self._interrupt_set = set(self._config.interrupt_words)
        else:
            self._backchanneling_set = {w.lower() for w in self._config.backchanneling_words}
            self._interrupt_set = {w.lower() for w in self._config.interrupt_words}

    @property
    def config(self) -> InterruptFilterConfig:
        return self._config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._config.enabled = value

    def add_backchanneling_word(self, word: str) -> None:
        normalized = word.lower() if not self._config.case_sensitive else word
        self._config.backchanneling_words.append(word)
        self._backchanneling_set.add(normalized)

    def add_interrupt_word(self, word: str) -> None:
        normalized = word.lower() if not self._config.case_sensitive else word
        self._config.interrupt_words.append(word)
        self._interrupt_set.add(normalized)

    def remove_backchanneling_word(self, word: str) -> None:
        normalized = word.lower() if not self._config.case_sensitive else word
        if word in self._config.backchanneling_words:
            self._config.backchanneling_words.remove(word)
        self._backchanneling_set.discard(normalized)

    def remove_interrupt_word(self, word: str) -> None:
        normalized = word.lower() if not self._config.case_sensitive else word
        if word in self._config.interrupt_words:
            self._config.interrupt_words.remove(word)
        self._interrupt_set.discard(normalized)

    def _contains_interrupt_phrase(self, text: str) -> bool:
        normalized = _normalize_text(text)

        for phrase in self._interrupt_set:
            if " " in phrase and phrase in normalized:
                return True

        return False

    def _is_only_backchanneling(self, text: str) -> bool:

        normalized = _normalize_text(text)

        for phrase in self._backchanneling_set:
            if " " in phrase:
                normalized = normalized.replace(phrase, " ")

        words = normalized.split()

        if not words:
            return True

        for word in words:
            if word and word not in self._backchanneling_set:
                return False

        return True

    def _contains_interrupt_word(self, text: str) -> bool:
        words = _split_into_words(text)
        for word in words:
            if word in self._interrupt_set:
                return True
        return False

    def should_interrupt(
        self,
        transcript: str,
        agent_is_speaking: bool,
    ) -> bool:

        if not self._config.enabled:
            return True  # No filtering, always interrupt

        transcript = transcript.strip()
        if not transcript:
            return False  # Empty transcript, no interrupt

        if not agent_is_speaking:
            logger.debug(
                "Interrupt filter: agent is silent, allowing input",
                extra={"transcript": transcript},
            )
            return True
        if self._contains_interrupt_phrase(transcript):
            logger.debug(
                "Interrupt filter: found interrupt phrase while speaking",
                extra={"transcript": transcript},
            )
            return True

        if self._contains_interrupt_word(transcript):
            logger.debug(
                "Interrupt filter: found interrupt word while speaking",
                extra={"transcript": transcript},
            )
            return True

        if self._is_only_backchanneling(transcript):
            logger.debug(
                "Interrupt filter: ignoring backchanneling while speaking",
                extra={"transcript": transcript},
            )
            return False

        logger.debug(
            "Interrupt filter: non-backchanneling input while speaking, allowing interrupt",
            extra={"transcript": transcript},
        )
        return True


_default_filter: InterruptFilter | None = None

def get_default_filter() -> InterruptFilter:
    global _default_filter
    if _default_filter is None:
        _default_filter = InterruptFilter()
    return _default_filter


def set_default_filter(filter: InterruptFilter) -> None:
    """Set the default global interrupt filter."""
    global _default_filter
    _default_filter = filter
