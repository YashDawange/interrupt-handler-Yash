"""
Intelligent Interruption Handling Filter

This module provides context-aware filtering of user input to distinguish between
"passive acknowledgements" (backchanneling) and "active interruptions" based on
whether the agent is currently speaking.

Key Features:
- Configurable ignore list of soft acknowledgement words
- Semantic interruption detection for mixed sentences
- Agent state awareness (speaking vs silent)
- Real-time processing with minimal latency
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..log import logger


@dataclass
class InterruptionFilterConfig:
    """Configuration for the interruption filter."""

    # Words/phrases to ignore when agent is speaking
    # These are treated as "soft" inputs that indicate listening but not interrupting
    ignore_on_speaking: list[str] = field(
        default_factory=lambda: [
            "yeah",
            "yep",
            "yes",
            "ok",
            "okay",
            "hmm",
            "hm",
            "uh-huh",
            "uhuh",
            "uh huh",
            "mm-hmm",
            "mmhm",
            "mm hmm",
            "right",
            "aha",
            "ah",
            "sure",
            "got it",
            "understood",
            "i see",
            "i understand",
            "mhm",
        ]
    )

    # Words that always trigger an interruption (command words)
    # These override the ignore list
    interrupt_keywords: list[str] = field(
        default_factory=lambda: [
            "wait",
            "stop",
            "hold on",
            "hold up",
            "pause",
            "no",
            "nope",
            "actually",
            "but wait",
            "but",
            "however",
            "yet",
            "though",
            "except",
            "unless",
            "meanwhile",
            "instead",
        ]
    )

    # Minimum confidence threshold for treating a word as valid
    min_word_confidence: float = 0.5

    # Whether to enable case-insensitive matching
    case_insensitive: bool = True


class InterruptionFilter:
    """
    Filters user input to implement intelligent interruption handling.

    The filter distinguishes between:
    1. Passive acknowledgements (e.g., "yeah", "ok", "hmm") when agent is speaking
    2. Active interruptions (e.g., "wait", "stop", "no") always
    3. Normal conversation when agent is silent

    The filter uses the agent's speaking state to make context-aware decisions.
    """

    def __init__(self, config: Optional[InterruptionFilterConfig] = None):
        """
        Initialize the interruption filter.

        Args:
            config: Optional InterruptionFilterConfig. Uses defaults if not provided.
        """
        self.config = config or InterruptionFilterConfig()
        self._compiled_ignore_pattern = self._compile_pattern(self.config.ignore_on_speaking)
        self._compiled_interrupt_pattern = self._compile_pattern(
            self.config.interrupt_keywords
        )

    def _compile_pattern(self, words: list[str]) -> re.Pattern[str]:
        """Compile a regex pattern for word matching."""
        # Escape special regex characters and create word boundary pattern
        escaped_words = [re.escape(word) for word in words]
        pattern = r"\b(" + "|".join(escaped_words) + r")\b"

        if self.config.case_insensitive:
            return re.compile(pattern, re.IGNORECASE)
        return re.compile(pattern)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for processing."""
        return text.strip().lower() if self.config.case_insensitive else text.strip()

    def _extract_words(self, text: str) -> list[str]:
        """Extract individual words from text, preserving order."""
        # Remove punctuation and split into words
        cleaned = re.sub(r"[^\w\s'-]", " ", text)
        words = cleaned.split()
        return [w.lower() if self.config.case_insensitive else w for w in words]

    def _contains_interrupt_keyword(self, text: str) -> bool:
        """Check if text contains any interrupt keywords."""
        normalized = self._normalize_text(text)
        match = self._compiled_interrupt_pattern.search(normalized)
        return match is not None

    def _contains_only_soft_words(self, text: str) -> bool:
        """
        Check if text contains ONLY soft acknowledgement words (no other content).

        This is important because phrases like "yeah wait" or "ok but" should
        trigger interruption due to the "wait" or "but" keywords, not be ignored.

        Args:
            text: The text to check

        Returns:
            True if the text is purely soft acknowledgements, False otherwise
        """
        words = self._extract_words(text)

        if not words:
            return False

        # Check each word against the ignore list
        for word in words:
            # Check if word matches any pattern in ignore list
            if not self._compiled_ignore_pattern.match(word):
                # Found a word that's not in the ignore list
                logger.debug(
                    f"non-soft word found in transcript",
                    extra={"word": word, "full_text": text},
                )
                return False

        return True

    def should_ignore_while_speaking(self, transcript: str) -> bool:
        """
        Determine if this transcript should be ignored while agent is speaking.

        Ignores the transcript if:
        1. It contains ONLY soft acknowledgement words (no interrupt keywords)
        2. It doesn't contain any interrupt keywords

        Args:
            transcript: The user's transcript

        Returns:
            True if the transcript should be ignored, False if it should interrupt
        """
        if not transcript or not transcript.strip():
            return True

        # First check for explicit interrupt keywords
        if self._contains_interrupt_keyword(transcript):
            logger.debug(
                "interrupt keyword detected in transcript",
                extra={"transcript": transcript},
            )
            return False

        # Check if only soft words are present
        if self._contains_only_soft_words(transcript):
            logger.debug(
                "soft-only acknowledgement detected, ignoring while speaking",
                extra={"transcript": transcript},
            )
            return True

        # Any other content should interrupt
        logger.debug(
            "non-soft content detected, will interrupt",
            extra={"transcript": transcript},
        )
        return False

    def process(
        self, transcript: str, *, agent_speaking: bool
    ) -> tuple[bool, Optional[str]]:
        """
        Process a user transcript and determine if it should trigger an interruption.

        This is the main entry point for the filter. It applies different rules
        based on the agent's state:

        - If agent is SPEAKING:
          - Soft acknowledgements (yeah, ok, hmm) → IGNORE (return False)
          - Any interrupt keyword → INTERRUPT (return True)
          - Mixed content → INTERRUPT (return True)

        - If agent is SILENT:
          - All valid input → PROCESS (return True)

        Args:
            transcript: The user's speech transcript
            agent_speaking: Whether the agent is currently speaking

        Returns:
            A tuple of (should_interrupt, filtered_transcript)
            - should_interrupt: True if this should trigger interruption, False if it should be ignored
            - filtered_transcript: The original or modified transcript (None if should be ignored)
        """
        if not transcript or not transcript.strip():
            return True, None

        if not agent_speaking:
            # Agent is silent - process all input normally
            logger.debug(
                "agent silent, processing transcript normally",
                extra={"transcript": transcript},
            )
            return True, transcript

        # Agent is speaking - apply soft word filtering
        logger.debug(
            "agent speaking, applying interruption filter",
            extra={"transcript": transcript, "agent_speaking": agent_speaking},
        )
        
        if self.should_ignore_while_speaking(transcript):
            # This is a soft acknowledgement, ignore it
            logger.info(
                f"FILTER: Ignoring soft word while agent speaking: '{transcript}'",
                extra={"transcript": transcript},
            )
            return False, None

        # This contains interrupt keywords or other content, should interrupt
        logger.info(
            f"FILTER: Interrupting agent for: '{transcript}'",
            extra={"transcript": transcript},
        )
        return True, transcript

    def get_config_summary(self) -> dict:
        """Get a summary of the filter configuration for logging/debugging."""
        return {
            "ignore_on_speaking_count": len(self.config.ignore_on_speaking),
            "interrupt_keywords_count": len(self.config.interrupt_keywords),
            "case_insensitive": self.config.case_insensitive,
            "min_word_confidence": self.config.min_word_confidence,
            "ignore_on_speaking_sample": self.config.ignore_on_speaking[:5],
            "interrupt_keywords_sample": self.config.interrupt_keywords[:5],
        }
