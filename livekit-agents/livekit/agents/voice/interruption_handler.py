"""
Intelligent Interruption Handler for LiveKit Agents

This module provides context-aware interruption handling that distinguishes between
passive acknowledgements (backchanneling) and active interruptions based on whether
the agent is currently speaking.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from ..log import logger

if TYPE_CHECKING:
    from .agent_session import AgentSession


class InterruptionHandler:
    """
    Handles intelligent interruption filtering based on agent state and user input.

    The handler distinguishes between:
    - Passive acknowledgements (backchanneling): "yeah", "ok", "hmm" - ignored when agent is speaking
    - Active interruptions: "wait", "stop", "no" - always interrupt
    - Mixed input: "yeah wait" - interrupts because it contains a command
    """

    # Default backchanneling words (passive acknowledgements)
    DEFAULT_BACKCHANNEL_WORDS = [
        "yeah",
        "ok",
        "okay",
        "hmm",
        "uh-huh",
        "uh huh",
        "right",
        "yep",
        "yup",
        "sure",
        "mhm",
        "mm-hmm",
        "mm hmm",
        "aha",
        "ah",
        "mhm",
        "uh",
        "um",
    ]

    # Default interrupt commands (always interrupt)
    DEFAULT_INTERRUPT_COMMANDS = [
        "wait",
        "stop",
        "no",
        "don't",
        "dont",
        "halt",
        "pause",
        "cancel",
        "abort",
    ]

    def __init__(
        self,
        backchannel_words: list[str] | None = None,
        interrupt_commands: list[str] | None = None,
        enabled: bool = True,
    ):
        """
        Initialize the interruption handler.

        Args:
            backchannel_words: List of words to ignore when agent is speaking.
                If None, uses default list or environment variable.
            interrupt_commands: List of words that always trigger interruption.
                If None, uses default list or environment variable.
            enabled: Whether the handler is enabled. Default True.
        """
        self.enabled = enabled

        # Load from environment variables if available
        if backchannel_words is None:
            env_words = os.getenv("LIVEKIT_AGENTS_BACKCHANNEL_WORDS")
            if env_words:
                backchannel_words = [w.strip().lower() for w in env_words.split(",")]
            else:
                backchannel_words = self.DEFAULT_BACKCHANNEL_WORDS.copy()

        if interrupt_commands is None:
            env_commands = os.getenv("LIVEKIT_AGENTS_INTERRUPT_COMMANDS")
            if env_commands:
                interrupt_commands = [w.strip().lower() for w in env_commands.split(",")]
            else:
                interrupt_commands = self.DEFAULT_INTERRUPT_COMMANDS.copy()

        # Normalize to lowercase for case-insensitive matching
        self.backchannel_words = {word.lower() for word in backchannel_words}
        self.interrupt_commands = {word.lower() for word in interrupt_commands}

        logger.debug(
            "InterruptionHandler initialized",
            extra={
                "enabled": self.enabled,
                "backchannel_words_count": len(self.backchannel_words),
                "interrupt_commands_count": len(self.interrupt_commands),
            },
        )

    def should_ignore_interruption(
        self, transcript: str, agent_is_speaking: bool
    ) -> bool:
        """
        Determine if an interruption should be ignored based on transcript and agent state.

        Args:
            transcript: The user's transcript text.
            agent_is_speaking: Whether the agent is currently speaking.

        Returns:
            True if the interruption should be ignored, False if it should proceed.
        """
        if not self.enabled:
            return False

        if not agent_is_speaking:
            # When agent is silent, never ignore - treat all input as valid
            return False

        if not transcript or not transcript.strip():
            # Empty transcript - don't ignore (let VAD handle it)
            return False

        # Normalize transcript for matching
        normalized_text = transcript.lower().strip()

        # Check if transcript contains any interrupt commands
        # Split into words and check each word
        words = self._extract_words(normalized_text)

        # If any interrupt command is present, always interrupt
        for word in words:
            if word in self.interrupt_commands:
                logger.debug(
                    "Interrupt command detected, allowing interruption",
                    extra={"transcript": transcript, "command": word},
                )
                return False

        # Check if transcript contains only backchanneling words
        # Remove punctuation and split into words
        all_backchannel = all(
            word in self.backchannel_words for word in words if word
        )

        if all_backchannel and words:
            logger.debug(
                "Backchanneling detected, ignoring interruption",
                extra={"transcript": transcript, "words": words},
            )
            return True

        # If transcript contains non-backchannel words, allow interruption
        return False

    def _extract_words(self, text: str) -> list[str]:
        """
        Extract words from text, handling punctuation and contractions.

        Args:
            text: Input text to extract words from.

        Returns:
            List of normalized words.
        """
        # Remove punctuation but keep apostrophes for contractions
        # Replace punctuation with spaces
        text = re.sub(r"[^\w\s'-]", " ", text)
        # Split on whitespace
        words = text.split()
        # Normalize and filter empty strings
        return [w.lower().strip() for w in words if w.strip()]

    def check_transcript_for_interrupt(self, transcript: str) -> bool:
        """
        Check if transcript contains interrupt commands (regardless of agent state).

        This is used for semantic interruption detection in mixed inputs.

        Args:
            transcript: The user's transcript text.

        Returns:
            True if transcript contains interrupt commands.
        """
        if not transcript or not transcript.strip():
            return False

        normalized_text = transcript.lower().strip()
        words = self._extract_words(normalized_text)

        return any(word in self.interrupt_commands for word in words)


def get_interruption_handler() -> InterruptionHandler:
    """
    Get or create the global interruption handler instance.

    Returns:
        InterruptionHandler instance.
    """
    if not hasattr(get_interruption_handler, "_instance"):
        enabled = os.getenv("LIVEKIT_AGENTS_INTELLIGENT_INTERRUPTION", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        get_interruption_handler._instance = InterruptionHandler(enabled=enabled)
    return get_interruption_handler._instance

