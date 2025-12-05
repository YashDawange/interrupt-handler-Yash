"""Intelligent interruption handling for LiveKit agents.

This module provides context-aware interruption handling that distinguishes
between passive acknowledgements (backchanneling) and active interruptions.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from ..log import logger

if TYPE_CHECKING:
    pass


class InterruptionHandler:
    """Handles intelligent interruption detection based on agent state and user input.

    This handler filters interruptions based on:
    - Whether the agent is currently speaking
    - Whether the user input contains only backchanneling words
    - Whether the user input contains interruption commands
    """

    def __init__(
        self,
        *,
        ignore_words: list[str] | None = None,
        interruption_commands: list[str] | None = None,
    ) -> None:
        """Initialize the interruption handler.

        Args:
            ignore_words: List of words to ignore when agent is speaking.
                Defaults to common backchanneling words.
            interruption_commands: List of words that should always trigger
                interruption. Defaults to common interruption commands.
        """
        # Default backchanneling words (passive acknowledgements)
        default_ignore_words = [
            "Yeah",
            "Yeah.",
            "OK.",
            "Okay.",
            "Mmm.",
            "Mmm.",
            "yes.",
            "ok",
            "okay.",
            "hmm.",
            "uh-huh.",
            "uh huh.",
            "right.",
            "sure.",
            "mhm",
            "mm-hmm",
            "mm hmm",
            "aha",
            "ah",
            "yep",
            "yup",
            "alright",
            "all right",
            "got it",
            "gotcha",
            "i see",
            "i understand",
        ]

        # Default interruption commands (active interruptions)
        default_interruption_commands = [
            "wait",
            "stop",
            "no",
            "hold on",
            "hold up",
            "pause",
            "cancel",
            "never mind",
            "nevermind",
            "actually",
            "but",
            "however",
            "correction",
            "wrong",
            "incorrect",
        ]

        self._ignore_words = set(
            (ignore_words if ignore_words is not None else default_ignore_words)
        )
        self._interruption_commands = set(
            (
                interruption_commands
                if interruption_commands is not None
                else default_interruption_commands
            )
        )

        # Load from environment variable if available
        env_ignore = os.getenv("LIVEKIT_AGENT_IGNORE_WORDS")
        if env_ignore:
            self._ignore_words.update(word.strip().lower() for word in env_ignore.split(","))

        env_commands = os.getenv("LIVEKIT_AGENT_INTERRUPTION_COMMANDS")
        if env_commands:
            self._interruption_commands.update(
                word.strip().lower() for word in env_commands.split(",")
            )

    def should_ignore_interruption(
        self, *, user_text: str, agent_is_speaking: bool
    ) -> bool:
        """Determine if an interruption should be ignored.

        The logic is simple:
        - ONLY ignore text that contains ONLY backchanneling words (yeah, ok, hmm, etc.)
        - Allow interruption for everything else (questions, commands, requests, etc.)

        Args:
            user_text: The transcribed user input text.
            agent_is_speaking: Whether the agent is currently speaking.

        Returns:
            True if the interruption should be ignored, False if it should be processed.
        """
        if not agent_is_speaking:
            # When agent is silent, never ignore user input
            return False

        if not user_text:
            # Empty text should not interrupt
            return True

        # Normalize text: lowercase, remove extra whitespace
        normalized_text = self._normalize_text(user_text)

        # Check if text contains ONLY ignore/backchanneling words
        # This is the ONLY case where we ignore the interruption
        if self._contains_only_ignore_words(normalized_text):
            logger.debug(
                f"Interruption ignored: text contains only backchanneling words: {user_text}"
            )
            return True

        # For all other text (questions, commands, requests, etc.), allow the interruption
        # This includes:
        # - Explicit interruption commands ("wait", "stop", "no")
        # - Mixed sentences ("yeah wait a second")
        # - Normal questions ("Can you explain more?")
        # - Any other meaningful input
        logger.debug(
            f"Interruption allowed: text contains meaningful content: {user_text}"
        )
        return False

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison.

        Args:
            text: Input text.

        Returns:
            Normalized text (lowercase, trimmed, single spaces).
        """
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation (but keep spaces)
        text = re.sub(r"[^\w\s]", " ", text)
        # Normalize whitespace
        text = " ".join(text.split())
        return text.strip()

    def _contains_interruption_command(self, text: str) -> bool:
        """Check if text contains any interruption command.

        Args:
            text: Normalized text.

        Returns:
            True if text contains an interruption command.
        """
        # Check for multi-word commands first (e.g., "hold on", "never mind")
        for command in self._interruption_commands:
            if " " in command:
                # Multi-word command - check if it appears in the text
                if command in text:
                    return True
        
        # Check individual words
        words = text.split()
        for word in words:
            if word in self._interruption_commands:
                return True
        return False

    def _contains_only_ignore_words(self, text: str) -> bool:
        """Check if text contains only ignore words.

        Args:
            text: Normalized text.

        Returns:
            True if text contains only ignore words.
        """
        if not text:
            return True

        words = text.split()
        if not words:
            return True

        # Check if all words are in the ignore list
        for word in words:
            if word not in self._ignore_words:
                return False

        return True

    def _has_interruption_intent(self, text: str) -> bool:
        """Check if text has interruption intent even if it contains ignore words.

        This handles cases like "Yeah wait a second" where the user says
        a backchanneling word but then adds an interruption command.

        Args:
            text: Normalized text.

        Returns:
            True if text has clear interruption intent.
        """
        # Check for interruption commands anywhere in the text
        if self._contains_interruption_command(text):
            return True

        # Check for patterns that indicate interruption intent
        interruption_patterns = [
            r"\b(but|however|actually|wait|stop|no)\b",
            r"\b(that's|that is)\s+(not|wrong|incorrect)",
            r"\b(i|we)\s+(need|want|think|believe)",
        ]

        for pattern in interruption_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False
    @property
    def ignore_words(self) -> set[str]:
        """Get the set of ignore words."""
        return self._ignore_words.copy()

    @property
    def interruption_commands(self) -> set[str]:
        """Get the set of interruption commands."""
        return self._interruption_commands.copy()

