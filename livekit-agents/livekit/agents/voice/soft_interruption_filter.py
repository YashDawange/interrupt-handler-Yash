"""Soft Interruption Filter

This module provides filtering logic to distinguish between passive acknowledgments
(soft interruptions like "yeah", "ok") and active interruptions (commands like "stop", "wait").
"""

import logging
import re
from typing import Sequence

logger = logging.getLogger(__name__)


class SoftInterruptionFilter:
    """Filter to detect and handle soft interruptions (backchanneling).

    Soft interruptions are passive acknowledgments that users make to indicate
    they are listening (e.g., "yeah", "ok", "hmm"). These should not interrupt
    the agent when it's actively speaking, but should be processed as valid input
    when the agent is silent.
    """

    # Default patterns for soft interruptions
    DEFAULT_SOFT_PATTERNS = [
        r"^yeah\.?$",
        r"^yep\.?$",
        r"^ok\.?$",
        r"^okay\.?$",
        r"^hmm+\.?$",
        r"^uh\s*huh\.?$",
        r"^mhm+\.?$",
        r"^right\.?$",
        r"^aha+\.?$",
        r"^sure\.?$",
        r"^alright\.?$",
        r"^got\s+it\.?$",
    ]

    def __init__(
        self,
        soft_patterns: Sequence[str] | None = None,
        case_sensitive: bool = False,
    ):
        """Initialize the soft interruption filter.

        Args:
            soft_patterns: List of regex patterns to match soft interruptions.
                          If None, uses DEFAULT_SOFT_PATTERNS.
            case_sensitive: Whether pattern matching should be case sensitive.
        """
        patterns = soft_patterns if soft_patterns is not None else self.DEFAULT_SOFT_PATTERNS

        flags = 0 if case_sensitive else re.IGNORECASE
        self._compiled_patterns = [
            re.compile(pattern, flags) for pattern in patterns
        ]
        self._case_sensitive = case_sensitive

    def is_soft_interruption(self, text: str) -> bool:
        """Check if the given text is a soft interruption.

        A soft interruption is one where the ENTIRE text matches one or more
        soft interruption patterns. Mixed inputs like "yeah wait" are NOT
        considered soft interruptions.

        Args:
            text: The transcript text to check

        Returns:
            True if the text is ONLY a soft interruption, False otherwise
        """
        if not text or not text.strip():
            return False

        # Normalize whitespace
        normalized_text = " ".join(text.split())

        # Check if entire text matches any soft pattern
        for pattern in self._compiled_patterns:
            if pattern.match(normalized_text):
                logger.debug(f"Matched pattern {pattern.pattern} for text: '{normalized_text}'")
                return True

        # Check for repeated soft words (e.g., "yeah yeah", "ok ok")
        # Split and check if all tokens are soft interruptions
        tokens = self._tokenize_text(normalized_text)
        if not tokens:
            return False

        # All tokens must be soft interruptions
        all_soft = all(self._is_single_token_soft(token) for token in tokens)

        if all_soft:
            logger.debug(f"All tokens are soft: {tokens}")
        else:
            logger.debug(f"Not all soft tokens: {tokens}")

        return all_soft

    def _tokenize_text(self, text: str) -> list[str]:
        """Tokenize text into words, removing punctuation."""
        # Simple tokenization - split on whitespace and strip punctuation
        tokens = text.split()
        cleaned_tokens = []

        for token in tokens:
            # Remove common punctuation
            cleaned = token.strip(".,!?;:")
            if cleaned:
                cleaned_tokens.append(cleaned)

        return cleaned_tokens

    def _is_single_token_soft(self, token: str) -> bool:
        """Check if a single token is a soft interruption."""
        # Check if this single token matches any of our compiled patterns
        for pattern in self._compiled_patterns:
            if pattern.match(token):
                return True

        # Fallback: check against simple word list for common soft words
        simple_soft_words = {
            "yeah", "yep", "ok", "okay", "hmm", "hm",
            "uh-huh", "mhm", "right", "aha", "sure", "alright"
        }

        check_token = token if self._case_sensitive else token.lower()
        return check_token in simple_soft_words

    def should_suppress_interruption(
        self,
        transcript: str,
        agent_is_speaking: bool,
    ) -> bool:
        """Determine if an interruption should be suppressed.

        This is the main decision function that implements the state-aware logic:
        - If agent is speaking AND input is soft interruption -> suppress (return True)
        - If agent is silent OR input is not soft interruption -> don't suppress (return False)

        Args:
            transcript: The user's transcript text
            agent_is_speaking: Whether the agent is currently speaking

        Returns:
            True if the interruption should be suppressed (ignored), False otherwise
        """
        # Only suppress if agent is speaking AND input is soft
        if agent_is_speaking and self.is_soft_interruption(transcript):
            return True

        return False
