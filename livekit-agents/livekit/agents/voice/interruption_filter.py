"""Intelligent interruption filtering for voice agents.

This module implements smart interruption handling that allows agents to:
1. Ignore backchannel words (e.g., "yeah", "ok") when speaking
2. Respond to genuine interruptions (e.g., "stop", "wait")
3. Handle semantic detection for mixed input (e.g., "yeah but wait")
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from livekit import rtc
from livekit.agents import stt, vad

from .interruption_config import InterruptionConfig

logger = logging.getLogger(__name__)

__all__ = ["InterruptionFilter", "InterruptionDecision", "PendingInterruption"]


class InterruptionDecision(str, Enum):
    """Decision outcomes for interruption handling."""

    IGNORE = "ignore"  # Ignore the interruption, continue speaking
    INTERRUPT = "interrupt"  # Stop speaking immediately
    RESPOND = "respond"  # Agent not speaking, respond normally
    PENDING = "pending"  # Waiting for STT confirmation


@dataclass
class PendingInterruption:
    """Represents an interruption that's waiting for STT confirmation."""

    timestamp: float
    vad_event: vad.VADEvent
    timeout_task: Optional[asyncio.Task] = None
    completed: bool = False


class InterruptionFilter:
    """Filters interruptions based on agent state and speech content.

    This filter implements context-aware interruption handling:
    - When agent is speaking: buffers VAD events and waits for STT
    - Analyzes transcription to determine if it's backchannel or genuine interruption
    - When agent is not speaking: passes through normally
    """

    def __init__(self, config: InterruptionConfig) -> None:
        """Initialize the interruption filter.

        Args:
            config: Configuration for backchannel words and interrupt keywords
        """
        self._config = config
        self._agent_state: str = "listening"
        self._pending_interruptions: list[PendingInterruption] = []
        self._lock = asyncio.Lock()

        logger.info(
            f"InterruptionFilter initialized with {len(config.backchannel_words)} backchannel words, "
            f"{len(config.interrupt_keywords)} interrupt keywords, timeout={config.stt_timeout}s"
        )

    @property
    def agent_state(self) -> str:
        """Get the current agent state."""
        return self._agent_state

    def update_agent_state(self, state: str) -> None:
        """Update the agent state.

        Args:
            state: New agent state (e.g., "speaking", "listening", "thinking")
        """
        old_state = self._agent_state
        self._agent_state = state

        if old_state != state:
            logger.debug(f"Agent state changed: {old_state} -> {state}")

            # If agent stopped speaking, clear pending interruptions
            if old_state == "speaking" and state != "speaking":
                asyncio.create_task(self._clear_pending_interruptions())

    async def on_vad_event(
        self, event: vad.VADEvent
    ) -> tuple[InterruptionDecision, Optional[vad.VADEvent]]:
        """Handle VAD event and decide whether to process it.

        Args:
            event: VAD event to process

        Returns:
            Tuple of (decision, event_to_process)
            - If decision is PENDING, event is buffered and None is returned
            - If decision is RESPOND, original event is returned
            - If decision is IGNORE, None is returned
        """
        if event.type != vad.VADEventType.START_OF_SPEECH:
            return InterruptionDecision.RESPOND, event

        async with self._lock:
            if self._agent_state == "speaking":
                # Agent is speaking, buffer the event and wait for STT
                pending = PendingInterruption(
                    timestamp=time.time(),
                    vad_event=event,
                )

                # Create timeout task
                pending.timeout_task = asyncio.create_task(
                    self._handle_timeout(pending)
                )

                self._pending_interruptions.append(pending)

                logger.debug(
                    f"Buffered VAD event while agent speaking (pending: {len(self._pending_interruptions)})"
                )

                return InterruptionDecision.PENDING, None
            else:
                # Agent not speaking, process normally
                logger.debug(f"Agent not speaking (state={self._agent_state}), processing VAD normally")
                return InterruptionDecision.RESPOND, event

    async def on_stt_event(
        self, transcript: str, is_final: bool = True
    ) -> InterruptionDecision:
        """Handle STT event and decide whether to interrupt.

        Args:
            transcript: Transcribed text from STT
            is_final: Whether this is a final transcript

        Returns:
            InterruptionDecision indicating what action to take
        """
        if not is_final:
            # Interim transcripts: return pending, wait for final
            return InterruptionDecision.PENDING

        async with self._lock:
            if not self._pending_interruptions:
                # No pending interruptions, nothing to analyze
                return InterruptionDecision.RESPOND

            # Get the oldest pending interruption
            pending = self._pending_interruptions[0]

            # Cancel the timeout task
            if pending.timeout_task and not pending.timeout_task.done():
                pending.timeout_task.cancel()

            # Mark as completed
            pending.completed = True

            # Analyze the transcript
            decision = self._analyze_transcript(transcript)

            logger.info(
                f"STT analysis: '{transcript}' -> {decision.value} "
                f"(agent_state={self._agent_state}, pending={len(self._pending_interruptions)})"
            )

            # Remove the processed pending interruption
            self._pending_interruptions.pop(0)

            return decision

    async def aclose(self) -> None:
        """Clean up resources and cancel pending tasks."""
        async with self._lock:
            # Cancel all pending timeout tasks
            for pending in self._pending_interruptions:
                if pending.timeout_task and not pending.timeout_task.done():
                    pending.timeout_task.cancel()
                    try:
                        await pending.timeout_task
                    except asyncio.CancelledError:
                        pass
            
            # Clear pending interruptions
            self._pending_interruptions.clear()

    def _analyze_transcript(self, transcript: str) -> InterruptionDecision:
        """Analyze transcript to determine if it's backchannel or interruption.

        Args:
            transcript: The transcribed text to analyze

        Returns:
            InterruptionDecision based on content analysis
        """
        # Normalize text
        text = transcript.strip()
        if not text:
            logger.debug("Empty transcript, ignoring")
            return InterruptionDecision.IGNORE

        if not self._config.case_sensitive:
            text = text.lower()

        # Split into words, removing punctuation
        import re

        words = re.findall(r"\b\w+\b", text)

        if not words:
            logger.debug("No words found in transcript, ignoring")
            return InterruptionDecision.IGNORE

        # Check if contains any interrupt keywords
        if self._contains_interrupt_keyword(words):
            logger.debug(f"Contains interrupt keyword: {words}")
            return InterruptionDecision.INTERRUPT

        # Check if all words are backchannel words
        if self._is_only_backchannel(words):
            logger.debug(f"Only backchannel words: {words}")
            return InterruptionDecision.IGNORE

        # Mixed input or unknown words - conservative approach: interrupt
        logger.debug(f"Mixed/unknown input: {words} - interrupting")
        return InterruptionDecision.INTERRUPT

    def _is_only_backchannel(self, words: list[str]) -> bool:
        """Check if all words are backchannel words.

        Args:
            words: List of words to check

        Returns:
            True if all words are in the backchannel list
        """
        if not words:
            return False

        normalized_words = [
            word.lower() if not self._config.case_sensitive else word
            for word in words
        ]

        return all(word in self._config.backchannel_words for word in normalized_words)

    def _contains_interrupt_keyword(self, words: list[str]) -> bool:
        """Check if any word is an interrupt keyword.

        Args:
            words: List of words to check

        Returns:
            True if any word is in the interrupt keywords list
        """
        if not words:
            return False

        normalized_words = [
            word.lower() if not self._config.case_sensitive else word
            for word in words
        ]

        return any(word in self._config.interrupt_keywords for word in normalized_words)

    async def _handle_timeout(self, pending: PendingInterruption) -> None:
        """Handle timeout for pending interruption.

        If STT doesn't respond within the timeout period, treat as genuine interruption.

        Args:
            pending: The pending interruption to handle
        """
        try:
            await asyncio.sleep(self._config.stt_timeout)

            async with self._lock:
                # Check if still pending
                if pending in self._pending_interruptions and not pending.completed:
                    logger.warning(
                        f"STT timeout ({self._config.stt_timeout}s) - treating as interruption"
                    )
                    pending.completed = True
                    # Note: The actual interruption will be handled by the agent activity
                    # This timeout just marks it as ready to interrupt
        except asyncio.CancelledError:
            # Timeout was cancelled (STT arrived in time)
            pass

    async def _clear_pending_interruptions(self) -> None:
        """Clear all pending interruptions when agent stops speaking."""
        async with self._lock:
            for pending in self._pending_interruptions:
                if pending.timeout_task and not pending.timeout_task.done():
                    pending.timeout_task.cancel()

            cleared = len(self._pending_interruptions)
            if cleared > 0:
                logger.debug(f"Cleared {cleared} pending interruptions")

            self._pending_interruptions.clear()

    def has_pending_interruptions(self) -> bool:
        """Check if there are any pending interruptions.

        Returns:
            True if there are pending interruptions waiting for STT
        """
        return len(self._pending_interruptions) > 0

    def get_pending_count(self) -> int:
        """Get the number of pending interruptions.

        Returns:
            Number of interruptions waiting for STT confirmation
        """
        return len(self._pending_interruptions)
