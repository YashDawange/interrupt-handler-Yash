"""Backchanneling detection module for filtering passive acknowledgements.

This module provides logic to distinguish between passive acknowledgements
(like "yeah", "ok", "hmm") and active interruptions when the agent is speaking.
"""

import re
from collections.abc import Sequence


class BackchannelingDetector:
    """Detects and filters backchanneling words from user input.

    Backchanneling words are passive acknowledgements that should be ignored
    when the agent is actively speaking, but treated as valid input when
    the agent is silent.
    """

    def __init__(
        self,
        *,
        filler_words: Sequence[str] | None = None,
        interruption_words: Sequence[str] | None = None,
    ) -> None:
        """Initialize the backchanneling detector.

        Args:
            filler_words: List of words to ignore when agent is speaking.
                Defaults to common backchanneling words.
            interruption_words: List of words that should always trigger
                interruption, even if mixed with filler words.
                Defaults to common interruption commands.
        """
        # Default filler words (passive acknowledgements)
        default_filler = self._default_filler_words()
        filler_list = filler_words if filler_words is not None else default_filler
        self._filler_words = {word.lower() for word in filler_list}

        # Default interruption words (active commands)
        default_interruption = self._default_interruption_words()
        interruption_list = (
            interruption_words if interruption_words is not None else default_interruption
        )
        self._interruption_words = {word.lower() for word in interruption_list}

    @staticmethod
    def _default_filler_words() -> list[str]:
        """Return default list of filler/backchanneling words."""
        return [
            "yeah",
            "yes",
            "yep",
            "yup",
            "ok",
            "okay",
            "hmm",
            "hmmm",
            "uh-huh",
            "uh huh",
            "right",
            "sure",
            "mhm",
            "mm-hmm",
            "mm hmm",
            "aha",
            "ah",
            "uh",
            "um",
            "alright",
            "got it",
            "gotcha",
            "i see",
            "i see",
            "understood",
            "okay",
        ]

    @staticmethod
    def _default_interruption_words() -> list[str]:
        """Return default list of interruption/command words."""
        return [
            "wait",
            "stop",
            "no",
            "hold on",
            "hold",
            "pause",
            "cancel",
            "nevermind",
            "never mind",
            "actually",
            "but",
            "however",
            "correction",
            "wrong",
            "incorrect",
        ]

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Remove punctuation and convert to lowercase
        text = re.sub(r"[^\w\s]", "", text.lower())
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _split_into_words(self, text: str) -> list[str]:
        """Split text into words, handling contractions and multi-word phrases."""
        normalized = self._normalize_text(text)
        words = normalized.split()
        return words

    def is_only_filler_words(self, text: str) -> bool:
        """Check if text contains only filler words.

        Args:
            text: The transcribed text to check.

        Returns:
            True if the text contains only filler words, False otherwise.
        """
        if not text or not text.strip():
            return False

        words = self._split_into_words(text)
        normalized_text = self._normalize_text(text)

        # Check if all words are filler words
        # Also check if the entire phrase matches a filler word (for multi-word fillers)
        all_filler = all(word in self._filler_words for word in words)
        phrase_is_filler = normalized_text in self._filler_words

        return all_filler or phrase_is_filler

    def contains_interruption_word(self, text: str) -> bool:
        """Check if text contains any interruption words.

        Args:
            text: The transcribed text to check.

        Returns:
            True if the text contains any interruption words, False otherwise.
        """
        if not text or not text.strip():
            return False

        words = self._split_into_words(text)
        normalized_text = self._normalize_text(text)

        # Check if any word is an interruption word
        has_interruption_word = any(word in self._interruption_words for word in words)
        # Also check if the entire phrase matches an interruption word
        phrase_is_interruption = normalized_text in self._interruption_words

        return has_interruption_word or phrase_is_interruption

    def should_ignore_interruption(self, text: str, agent_is_speaking: bool) -> bool:
        """Determine if an interruption should be ignored based on context.

        Args:
            text: The transcribed user input.
            agent_is_speaking: Whether the agent is currently speaking.

        Returns:
            True if the interruption should be ignored (agent continues speaking),
            False if the interruption should be allowed (agent stops).
        """
        if not agent_is_speaking:
            # When agent is silent, never ignore user input
            return False

        # If text contains interruption words, never ignore
        if self.contains_interruption_word(text):
            return False

        # If text is only filler words and agent is speaking, ignore it
        if self.is_only_filler_words(text):
            return True

        # Default: allow interruption for any other input
        return False
