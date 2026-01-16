"""
Intelligent Interruption Handler for LiveKit Voice Agents.

This module provides sophisticated interruption handling that can differentiate
between filler words (like "yeah", "ok", "hmm") and real commands (like "stop", "wait").
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Callable

from ..log import logger


@dataclass
class InterruptionDecision:
    """Represents a decision about whether to interrupt the agent."""

    should_interrupt: bool
    """Whether the agent should be interrupted."""

    reason: str
    """Human-readable reason for the decision."""

    is_pending: bool = False
    """Whether this is a pending decision waiting for STT confirmation."""


class InterruptionHandler:
    """
    Handles intelligent interruption logic for voice agents.

    This handler can differentiate between:
    - Filler words ("yeah", "ok", "hmm") that should be ignored while agent is speaking
    - Command words ("stop", "wait", "no") that should always interrupt
    - Mixed input ("yeah but wait") that should interrupt
    - Regular speech that should interrupt when detected

    Key behaviors:
    - Agent silent + filler words → treat as valid input
    - Agent speaking + filler words → ignore, continue speaking seamlessly
    - Agent speaking + command words → interrupt immediately
    - Agent speaking + mixed input → interrupt
    """

    # Default filler words that should be ignored when agent is speaking
    DEFAULT_IGNORE_WORDS = frozenset(
        [
            "yeah",
            "ok",
            "hmm",
            "uh-huh",
            "right",
            "aha",
            "mhm",
            "yep",
            "yup",
            "mm",
            "uh",
            "um",
        ]
    )

    # Command words that should always trigger interruption
    DEFAULT_COMMAND_WORDS = frozenset(
        [
            "stop",
            "wait",
            "no",
            "pause",
            "hold",
            "hold on",
            "hang on",
        ]
    )

    def __init__(
        self,
        ignore_words: frozenset[str] | None = None,
        command_words: frozenset[str] | None = None,
        enable_env_config: bool = True,
    ):
        """
        Initialize the interruption handler.

        Args:
            ignore_words: Set of filler words to ignore. Defaults to DEFAULT_IGNORE_WORDS.
            command_words: Set of command words that always interrupt. Defaults to DEFAULT_COMMAND_WORDS.
            enable_env_config: Whether to load configuration from environment variables.
        """
        self._agent_is_speaking = False
        self._pending_interrupt = False
        self._pending_interrupt_lock = asyncio.Lock()

        # Configure ignore words
        if ignore_words is not None:
            self._ignore_words = ignore_words
        elif enable_env_config and (env_ignore := os.getenv("LIVEKIT_IGNORE_WORDS")):
            self._ignore_words = frozenset(w.strip().lower() for w in env_ignore.split(","))
        else:
            self._ignore_words = self.DEFAULT_IGNORE_WORDS

        # Configure command words
        if command_words is not None:
            self._command_words = command_words
        elif enable_env_config and (env_commands := os.getenv("LIVEKIT_COMMAND_WORDS")):
            self._command_words = frozenset(w.strip().lower() for w in env_commands.split(","))
        else:
            self._command_words = self.DEFAULT_COMMAND_WORDS

        logger.info(
            f"Interruption handler initialized with {len(self._ignore_words)} ignore words "
            f"and {len(self._command_words)} command words",
            extra={
                "ignore_words": list(self._ignore_words),
                "command_words": list(self._command_words),
            },
        )

    @property
    def agent_is_speaking(self) -> bool:
        """Check if the agent is currently speaking."""
        return self._agent_is_speaking

    @property
    def ignore_words(self) -> frozenset[str]:
        """Get the set of ignore words."""
        return self._ignore_words

    @property
    def command_words(self) -> frozenset[str]:
        """Get the set of command words."""
        return self._command_words

    def set_agent_speaking(self, is_speaking: bool) -> None:
        """
        Update the agent's speaking state.

        Args:
            is_speaking: True when agent starts speaking, False when it stops.
        """
        if self._agent_is_speaking != is_speaking:
            self._agent_is_speaking = is_speaking
            logger.debug(
                f"Agent speaking state changed: {is_speaking}",
                extra={"agent_speaking": is_speaking},
            )

    async def on_vad_event(self) -> InterruptionDecision:
        """
        Handle VAD (Voice Activity Detection) event.

        This is called when the VAD detects user speech. If the agent is speaking,
        we mark a pending interrupt but don't stop audio yet. We wait for the STT
        result to decide whether to confirm or discard the interruption.

        Returns:
            InterruptionDecision indicating whether to interrupt immediately or wait.
        """
        async with self._pending_interrupt_lock:
            if self._agent_is_speaking:
                self._pending_interrupt = True
                logger.info(
                    "Pending interrupt triggered - waiting for STT confirmation",
                    extra={"agent_speaking": True},
                )
                return InterruptionDecision(
                    should_interrupt=False,
                    reason="Pending interrupt - waiting for STT to confirm",
                    is_pending=True,
                )
            else:
                logger.debug(
                    "VAD event while agent silent - allow normal processing",
                    extra={"agent_speaking": False},
                )
                return InterruptionDecision(
                    should_interrupt=True, reason="Agent is silent - process normally"
                )

    async def on_stt_result(self, transcript: str) -> InterruptionDecision:
        """
        Handle STT (Speech-to-Text) result.

        This is called when we receive the transcribed text. If there's a pending
        interrupt, we analyze the transcript to decide whether to confirm or discard it.

        Decision logic:
        1. If transcript contains any command words → INTERRUPT
        2. If transcript contains only ignore words → DISCARD INTERRUPT
        3. Otherwise → INTERRUPT (treat as real speech)

        Args:
            transcript: The transcribed text from the user's speech.

        Returns:
            InterruptionDecision indicating whether to interrupt based on the transcript.
        """
        async with self._pending_interrupt_lock:
            if not self._pending_interrupt:
                # No pending interrupt, nothing to decide
                return InterruptionDecision(
                    should_interrupt=False, reason="No pending interrupt"
                )

            # Reset pending flag
            self._pending_interrupt = False

            # Normalize transcript
            normalized_text = self._normalize_text(transcript)

            if not normalized_text:
                logger.debug(
                    "Empty transcript - discarding interrupt",
                    extra={"transcript": transcript},
                )
                return InterruptionDecision(
                    should_interrupt=False, reason="Empty transcript"
                )

            # Check if transcript contains any command words
            if self._contains_command_words(normalized_text):
                logger.info(
                    f"Command detected in transcript - interrupting agent: '{transcript}'",
                    extra={"transcript": transcript, "normalized": normalized_text},
                )
                return InterruptionDecision(
                    should_interrupt=True,
                    reason=f"Command words detected: '{transcript}'",
                )

            # Check if transcript contains ONLY ignore words
            if self._is_only_ignore_words(normalized_text):
                logger.info(
                    f"Ignore filler while speaking: '{transcript}'",
                    extra={"transcript": transcript, "normalized": normalized_text},
                )
                return InterruptionDecision(
                    should_interrupt=False,
                    reason=f"Only filler words detected: '{transcript}'",
                )

            # Transcript contains real speech (not just fillers) - interrupt
            logger.info(
                f"Real speech detected - interrupting agent: '{transcript}'",
                extra={"transcript": transcript, "normalized": normalized_text},
            )
            return InterruptionDecision(
                should_interrupt=True, reason=f"Real speech detected: '{transcript}'"
            )

    def reset_pending_interrupt(self) -> None:
        """
        Reset the pending interrupt flag.

        This can be called externally if the interrupt state needs to be cleared.
        """
        self._pending_interrupt = False
        logger.debug("Pending interrupt flag reset")

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.

        Converts to lowercase, removes punctuation, and splits into words.

        Args:
            text: The text to normalize.

        Returns:
            Normalized text as a string.
        """
        # Convert to lowercase
        text = text.lower().strip()

        # Remove punctuation (keep spaces and hyphens)
        text = re.sub(r"[^\w\s-]", " ", text)

        # Normalize whitespace
        text = " ".join(text.split())

        return text

    def _contains_command_words(self, normalized_text: str) -> bool:
        """
        Check if the text contains any command words.

        Args:
            normalized_text: The normalized text to check.

        Returns:
            True if any command word is found in the text.
        """
        words = normalized_text.split()

        # Check for single-word commands
        for word in words:
            if word in self._command_words:
                return True

        # Check for multi-word commands (like "hold on", "hang on")
        text_normalized = " " + normalized_text + " "
        for command in self._command_words:
            if " " in command:  # Multi-word command
                if " " + command + " " in text_normalized or text_normalized.startswith(
                    command + " "
                ):
                    return True

        return False

    def _is_only_ignore_words(self, normalized_text: str) -> bool:
        """
        Check if the text contains ONLY ignore words (filler words).

        Args:
            normalized_text: The normalized text to check.

        Returns:
            True if the text consists entirely of ignore words.
        """
        if not normalized_text:
            return False

        words = normalized_text.split()

        # All words must be in ignore list
        for word in words:
            if word not in self._ignore_words:
                return False

        return len(words) > 0


def create_interruption_handler(
    ignore_words: list[str] | None = None,
    command_words: list[str] | None = None,
    enable_env_config: bool = True,
) -> InterruptionHandler:
    """
    Factory function to create an InterruptionHandler.

    Args:
        ignore_words: List of filler words to ignore. Defaults to built-in list.
        command_words: List of command words that always interrupt. Defaults to built-in list.
        enable_env_config: Whether to load configuration from environment variables.

    Returns:
        A configured InterruptionHandler instance.
    """
    ignore_set = frozenset(w.lower() for w in ignore_words) if ignore_words else None
    command_set = frozenset(w.lower() for w in command_words) if command_words else None

    return InterruptionHandler(
        ignore_words=ignore_set,
        command_words=command_set,
        enable_env_config=enable_env_config,
    )
