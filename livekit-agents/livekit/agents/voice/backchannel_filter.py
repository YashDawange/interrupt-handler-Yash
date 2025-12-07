from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..log import logger
from ..tokenize.basic import split_words

if TYPE_CHECKING:
    from .agent_session import AgentSession

# Default ignore words (backchanneling/filler words)
DEFAULT_IGNORE_WORDS = [
    "yeah",
    "ok",
    "okay",
    "hmm",
    "hmmm",
    "right",
    "uh-huh",
    "uh huh",
    "aha",
    "mhm",
    "mm-hmm",
    "mm hmm",
    "yep",
    "yup",
    "sure",
    "got it",
    "gotcha",
    "alright",
    "all right",
]

# Default command words that should always trigger interruption
DEFAULT_COMMAND_WORDS = [
    "wait",
    "stop",
    "no",
    "hold on",
    "pause",
    "cancel",
    "nevermind",
    "never mind",
    "don't",
    "dont",
    "not",
    "wrong",
    "incorrect",
]


class BackchannelFilter:
    """Filters backchanneling words to prevent false interruptions when agent is speaking.

    When the agent is speaking, user utterances containing only backchanneling words
    (like "yeah", "ok", "hmm") should be ignored. However, if the utterance contains
    command words (like "wait", "stop", "no"), the agent should interrupt.

    This filter only applies when the agent is actively speaking. When the agent is
    silent, all user input is treated as valid.
    """

    def __init__(
        self,
        ignore_words: list[str] | None = None,
        command_words: list[str] | None = None,
        case_sensitive: bool = False,
    ) -> None:
        """Initialize the backchannel filter.

        Args:
            ignore_words: List of words/phrases to ignore when agent is speaking.
                Defaults to common backchanneling words.
            command_words: List of words/phrases that should always trigger interruption.
                Defaults to common command words.
            case_sensitive: Whether word matching should be case-sensitive.
                Defaults to False.
        """
        self._ignore_words = (ignore_words or DEFAULT_IGNORE_WORDS).copy()
        self._command_words = (command_words or DEFAULT_COMMAND_WORDS).copy()
        self._case_sensitive = case_sensitive

        # Normalize words for matching
        if not case_sensitive:
            self._ignore_words = [w.lower() for w in self._ignore_words]
            self._command_words = [w.lower() for w in self._command_words]

        # Sort by length (longest first) to match phrases before individual words
        self._ignore_words.sort(key=len, reverse=True)
        self._command_words.sort(key=len, reverse=True)

    def should_ignore_interruption(
        self, transcript: str, agent_state: str
    ) -> bool:
        """Determine if an interruption should be ignored based on transcript and agent state.

        Args:
            transcript: The user's transcribed text (may include interim transcript).
            agent_state: Current state of the agent ("speaking", "listening", etc.).

        Returns:
            True if the interruption should be ignored (agent should continue speaking),
            False if the interruption should proceed (agent should stop).
        """
        # Only filter when agent is speaking
        if agent_state != "speaking":
            return False

        # If no transcript, we can't filter - allow interruption to proceed
        # (This handles the case where VAD triggers before STT has transcribed)
        if not transcript or not transcript.strip():
            return False

        # Normalize transcript for matching
        normalized_transcript = transcript if self._case_sensitive else transcript.lower()
        normalized_transcript = normalized_transcript.strip()

        # Check for command words first (these should always interrupt)
        if self._contains_command_word(normalized_transcript):
            logger.debug(
                "BackchannelFilter: Command word detected, allowing interruption",
                extra={"transcript": transcript},
            )
            return False  # Don't ignore - allow interruption

        # Check if transcript contains only ignore words
        if self._contains_only_ignore_words(normalized_transcript):
            logger.debug(
                "BackchannelFilter: Only ignore words detected, ignoring interruption",
                extra={"transcript": transcript},
            )
            return True  # Ignore the interruption

        # If transcript contains both ignore words and other words, don't ignore
        # (e.g., "yeah but wait" should interrupt because of "wait")
        logger.debug(
            "BackchannelFilter: Mixed content detected, allowing interruption",
            extra={"transcript": transcript},
        )
        return False  # Don't ignore - allow interruption

    def _contains_command_word(self, text: str) -> bool:
        """Check if text contains any command words."""
        # Check for phrase matches first (longest first)
        for phrase in self._command_words:
            if phrase in text:
                return True

        # Also check individual words
        words = split_words(text, split_character=True)
        # split_words returns tuples (word, start, end), extract just the word
        word_set = {w[0].lower() if not self._case_sensitive else w[0] for w in words}
        return any(cmd in word_set for cmd in self._command_words)

    def _contains_only_ignore_words(self, text: str) -> bool:
        """Check if text contains only ignore words (and punctuation)."""
        # Normalize text: convert hyphens to spaces, then remove other punctuation
        # This handles "uh-huh" -> "uh huh" for matching
        text_normalized = text.replace("-", " ").replace("_", " ")
        # Remove punctuation for matching, keep spaces to preserve phrase boundaries
        text_clean = re.sub(r"[^\w\s]", "", text_normalized)
        text_clean = text_clean.strip()

        if not text_clean:
            return False

        # Normalize ignore words too (remove hyphens for matching)
        # Check for phrase matches first (longest first)
        remaining_text = text_clean
        for phrase in self._ignore_words:
            # Normalize phrase (remove hyphens) for matching
            phrase_normalized = phrase.replace("-", " ").replace("_", " ").strip()
            # Replace all occurrences of normalized phrase with space
            remaining_text = remaining_text.replace(phrase_normalized, " ")
            remaining_text = remaining_text.strip()

        # Check if only ignore words remain (split into words and check)
        words = split_words(remaining_text, split_character=True)
        # split_words returns tuples (word, start, end), extract just the word
        remaining_words = [
            w[0].lower() if not self._case_sensitive else w[0]
            for w in words
            if w[0].strip()
        ]

        # If no words remain, text contained only ignore words
        if not remaining_words:
            return True

        # Check if remaining words are also ignore words (handles cases like "yeah ok")
        remaining_word_set = set(remaining_words)
        ignore_word_set = set(self._ignore_words)

        # Check if all remaining words are in ignore list
        return remaining_word_set.issubset(ignore_word_set)

