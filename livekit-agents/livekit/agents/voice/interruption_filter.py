from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from ..log import logger

if TYPE_CHECKING:
    pass


class InterruptionFilter:
    """
    Intelligent interruption filter that distinguishes between:
    - Passive acknowledgements (backchanneling) that should not interrupt
    - Active interruptions that should stop agent speech
    - Normal responses when agent is silent
    """

    # Default backchannel words that should be ignored during agent speech
    # Default backchannel words that should be ignored during agent speech
    DEFAULT_BACKCHANNEL_WORDS = {
        "yeah",
        "ok",
        "okay",
        "hmm",
        "uh-huh",
        "mm-hmm",
        "right",
        "yes",
        "yep",
        "sure",
        "aha",
        "ah",
        "mhm",
        "mm",
        "uh",
        "um",
        "got it",
        "alright",
        "gotcha",
        "okay, got it",
        "understood",
        "i see",
        "absolutely",
        "definitely",
        "roger that",
        "make sense",
    }

    # Words that always indicate interruption intent
    DEFAULT_INTERRUPTION_WORDS = {
        "wait",
        "stop",
        "hold on",
        "no",
        "but",
        "actually",
        "however",
        "excuse me",
        "sorry",
        "pardon",
        "let me",
        "can i",
        "i want",
        "i need",
        "what about",
        "how about",
        "what if",
    }

    def __init__(
        self,
        *,
        backchannel_words: set[str] | None = None,
        interruption_words: set[str] | None = None,
        case_sensitive: bool = False,
        min_words_for_interruption: int = 1,
    ):
        """
        Initialize the interruption filter.

        Args:
            backchannel_words: Custom set of backchannel words to ignore during speech
            interruption_words: Custom set of words that always trigger interruption
            case_sensitive: Whether word matching should be case sensitive
            min_words_for_interruption: Minimum number of words needed for interruption
        """
        self.backchannel_words = (
            backchannel_words or self.DEFAULT_BACKCHANNEL_WORDS.copy()
        )
        self.interruption_words = (
            interruption_words or self.DEFAULT_INTERRUPTION_WORDS.copy()
        )
        self.case_sensitive = case_sensitive
        self.min_words_for_interruption = min_words_for_interruption

        # Pre-compile regex patterns for efficiency
        if not case_sensitive:
            self.backchannel_words = {word.lower() for word in self.backchannel_words}
            self.interruption_words = {word.lower() for word in self.interruption_words}

    def should_interrupt(
        self, transcript: str, agent_state: Literal["speaking", "silent", "thinking"]
    ) -> tuple[bool, str]:
        """
        Determine if a transcript should cause an interruption based on agent state.

        Args:
            transcript: The user's transcribed speech
            agent_state: Current state of the agent

        Returns:
            Tuple of (should_interrupt, reason)
        """
        if not transcript or not transcript.strip():
            return False, "empty_transcript"

        # Normalize transcript for analysis
        normalized_text = transcript.lower() if not self.case_sensitive else transcript
        words = self._extract_words(normalized_text)

        logger.debug(
            f"Interrupt filter processing: '{transcript}' | Agent: {agent_state} | Words: {words}"
        )

        # Check for explicit interruption words first (always interrupt)
        if self._contains_interruption_words(words):
            logger.debug(f"Interruption detected: contains interruption words")
            return True, "interruption_word_detected"

        # If agent is silent, process all inputs normally
        if agent_state != "speaking":
            logger.debug(f"Agent not speaking, allowing input")
            return True, "agent_silent"

        # Agent is speaking - apply intelligent filtering
        if self._is_pure_backchannel(words):
            logger.debug(f"Pure backchannel detected, ignoring during speech")
            return False, "backchannel_ignored"

        # Mixed content or non-backchannel - allow interruption
        if len(words) >= self.min_words_for_interruption:
            logger.debug(f"Substantial input detected, allowing interruption")
            return True, "substantial_input"

        # Too short and not pure backchannel
        logger.debug(f"Input too short, ignoring")
        return False, "input_too_short"

    def _extract_words(self, text: str) -> list[str]:
        """Extract meaningful words from text, removing punctuation."""
        # Remove punctuation and split into words
        words = re.findall(
            r"\b\w+\b", text.lower() if not self.case_sensitive else text
        )
        return words

    def _contains_interruption_words(self, words: list[str]) -> bool:
        """Check if any interruption words are present."""
        word_set = set(words)
        return bool(word_set.intersection(self.interruption_words))

    def _is_pure_backchannel(self, words: list[str]) -> bool:
        """Check if the input consists only of backchannel words."""
        if not words:
            return False

        # All words must be backchannel words
        word_set = set(words)
        non_backchannel = word_set - self.backchannel_words

        return len(non_backchannel) == 0

    def add_backchannel_word(self, word: str) -> None:
        """Add a custom backchannel word."""
        processed_word = word.lower() if not self.case_sensitive else word
        self.backchannel_words.add(processed_word)

    def add_interruption_word(self, word: str) -> None:
        """Add a custom interruption word."""
        processed_word = word.lower() if not self.case_sensitive else word
        self.interruption_words.add(processed_word)

    def remove_backchannel_word(self, word: str) -> None:
        """Remove a backchannel word."""
        processed_word = word.lower() if not self.case_sensitive else word
        self.backchannel_words.discard(processed_word)

    def remove_interruption_word(self, word: str) -> None:
        """Remove an interruption word."""
        processed_word = word.lower() if not self.case_sensitive else word
        self.interruption_words.discard(processed_word)
