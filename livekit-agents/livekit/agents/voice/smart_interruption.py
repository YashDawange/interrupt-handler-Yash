"""
Smart Interruption Filter

This module provides intelligent filtering of voice interruptions to distinguish between:
1. Backchannel feedback (e.g., "yeah", "okay", "hmm") - passive listening signals
2. Explicit interruptions (e.g., "stop", "wait", "no") - active commands to interrupt

The filter prevents agents from stopping mid-speech when users provide backchannel
acknowledgments, while still allowing explicit interruption commands.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Default lists of words to ignore vs interrupt
DEFAULT_IGNORE_LIST = {
    "yeah",
    "yup",
    "yes",
    "ok",
    "okay",
    "hmm",
    "mm",
    "mmm",
    "mm-hmm",
    "uh-huh",
    "mhmm",
    "hm",
    "ah",
    "ohh",
    "right",
    "aha",
    "ya",
    "yep",
}

DEFAULT_INTERRUPT_LIST = {
    "stop",
    "wait",
    "no",
    "hold",
    "pause",
    "but",
}


class SmartInterruptionFilter:
    """
    Filters interruptions based on transcript content to distinguish between
    backchannel feedback and explicit interruption commands.
    """

    def __init__(
        self,
        ignore_list: Optional[set[str]] = None,
        interrupt_list: Optional[set[str]] = None,
        max_words: int = 3,
    ):
        """
        Initialize the smart interruption filter.

        Args:
            ignore_list: Set of words to ignore (backchannel words)
            interrupt_list: Set of words that trigger interruption
            max_words: Maximum word count for backchannel classification
        """
        self.ignore_list = ignore_list or DEFAULT_IGNORE_LIST
        self.interrupt_list = interrupt_list or DEFAULT_INTERRUPT_LIST
        self.max_words = max_words

    def normalize_text(self, text: str) -> str:
        """Remove punctuation and convert to lowercase."""
        # Remove punctuation and extra whitespace
        text = re.sub(r"[^\w\s-]", "", text.lower())
        return " ".join(text.split())

    def tokenize(self, text: str) -> list[str]:
        """Split text into words."""
        return text.split()

    def is_pure_backchannel(self, words: list[str]) -> bool:
        """
        Check if all words are in the ignore list (backchannel).

        Args:
            words: List of normalized words

        Returns:
            True if all words are backchannel words
        """
        if not words:
            return False

        # Must be short (max_words or fewer)
        if len(words) > self.max_words:
            return False

        # All words must be in ignore list
        return all(word in self.ignore_list for word in words)

    def contains_interrupt_word(self, words: list[str]) -> bool:
        """
        Check if any word is an explicit interrupt command.

        Args:
            words: List of normalized words

        Returns:
            True if contains interrupt word
        """
        return any(word in self.interrupt_list for word in words)

    def should_interrupt(
        self, transcript: str, agent_is_speaking: bool, is_final: bool = True
    ) -> bool:
        """
        Determine if the transcript should trigger an interruption.

        Logic:
        1. If agent is NOT speaking, always process normally (not an interruption context)
        2. If agent IS speaking:
           a. Check for explicit interrupt words → always interrupt
           b. Check if pure backchannel (short, all ignore words) → don't interrupt
           c. Otherwise → interrupt (mixed input, long input, etc.)

        Args:
            transcript: The user's speech transcript
            agent_is_speaking: Whether the agent is currently speaking
            is_final: Whether this is the final transcript (vs interim)

        Returns:
            True if should interrupt the agent, False if should ignore
        """
        # Not an interruption context if agent isn't speaking
        if not agent_is_speaking:
            return True  # Process normally

        # Only filter on final transcripts for accuracy
        if not is_final:
            return False  # Don't decide on interim transcripts

        # Normalize and tokenize
        normalized = self.normalize_text(transcript)
        words = self.tokenize(normalized)

        if not words:
            return False

        # Check for explicit interrupt commands first
        if self.contains_interrupt_word(words):
            logger.debug(
                f"Smart interruption: INTERRUPT - contains interrupt word",
                extra={"transcript": transcript, "words": words},
            )
            return True

        # Check if it's pure backchannel
        if self.is_pure_backchannel(words):
            logger.debug(
                f"Smart interruption: IGNORE - pure backchannel",
                extra={"transcript": transcript, "words": words},
            )
            return False

        # Mixed input or longer phrases → interrupt
        logger.debug(
            f"Smart interruption: INTERRUPT - mixed/long input",
            extra={"transcript": transcript, "words": words, "word_count": len(words)},
        )
        return True
