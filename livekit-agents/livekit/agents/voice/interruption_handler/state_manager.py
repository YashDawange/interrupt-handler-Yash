"""
Agent State Manager for Interruption Handling

Tracks the agent's current speaking state to enable context-aware
interruption decisions. This module provides a clean interface
to query the agent's state and manage state transitions.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from ...log import logger


@dataclass
class AgentStateSnapshot:
    """Immutable snapshot of agent state at a point in time."""
    
    is_speaking: bool
    """Whether the agent is currently speaking."""
    
    utterance_id: Optional[str] = None
    """Unique identifier for the current utterance."""
    
    speech_start_time: Optional[float] = None
    """Timestamp when the current speech started."""
    
    speech_duration: Optional[float] = None
    """Duration of current speech in seconds."""
    
    def to_dict(self) -> dict:
        """Convert state to dictionary."""
        return {
            "is_speaking": self.is_speaking,
            "utterance_id": self.utterance_id,
            "speech_start_time": self.speech_start_time,
            "speech_duration": self.speech_duration,
        }


class AgentStateManager:
    """
    Thread-safe state manager for tracking agent speaking state.
    
    This manager maintains the agent's current state and provides methods
    to transition between states. It's designed to work with LiveKit's
    agent event loop and supports concurrent access.
    
    Example:
        >>> state_mgr = AgentStateManager()
        >>> state_mgr.start_speaking(utterance_id="utt_123")
        >>> state = state_mgr.get_state()
        >>> print(state.is_speaking)  # True
        >>> await state_mgr.stop_speaking()
        >>> state = state_mgr.get_state()
        >>> print(state.is_speaking)  # False
    """
    
    def __init__(self, auto_timeout: Optional[float] = None) -> None:
        """
        Initialize the state manager.
        
        Args:
            auto_timeout: Optional timeout in seconds. If set, the state
                         manager will automatically transition to non-speaking
                         after this duration. Useful for safety (default: None).
        """
        self._lock = asyncio.Lock()
        self._is_speaking = False
        self._utterance_id: Optional[str] = None
        self._speech_start_time: Optional[float] = None
        self._auto_timeout = auto_timeout
        self._timeout_task: Optional[asyncio.Task[None]] = None
        
        logger.debug(
            f"AgentStateManager initialized (auto_timeout={auto_timeout})"
        )
    
    async def start_speaking(
        self,
        utterance_id: str,
        auto_cancel_timeout: bool = True,
    ) -> None:
        """
        Mark the agent as starting to speak.
        
        Args:
            utterance_id: Unique identifier for this utterance/speech segment.
                         Can be a TTS generation ID or custom identifier.
            auto_cancel_timeout: If True, cancel any pending auto-timeout
                                (default: True).
        
        Raises:
            ValueError: If utterance_id is empty.
        """
        if not utterance_id:
            raise ValueError("utterance_id cannot be empty")
        
        async with self._lock:
            # Cancel any pending timeout from previous speech
            if auto_cancel_timeout and self._timeout_task:
                self._timeout_task.cancel()
                self._timeout_task = None
            
            self._is_speaking = True
            self._utterance_id = utterance_id
            self._speech_start_time = time.time()
            
            # Schedule auto-timeout if configured
            if self._auto_timeout is not None:
                self._timeout_task = asyncio.create_task(
                    self._auto_timeout_speech()
                )
            
            logger.debug(
                f"Agent started speaking (utterance_id={utterance_id})"
            )
    
    async def stop_speaking(self, force: bool = False) -> None:
        """
        Mark the agent as stopping speech.
        
        Args:
            force: If True, immediately stop regardless of locks.
                  If False, respects the async lock (default: False).
        """
        if force:
            # Force stop without waiting for lock
            await self._stop_speaking_internal()
        else:
            async with self._lock:
                await self._stop_speaking_internal()
    
    async def _stop_speaking_internal(self) -> None:
        """Internal method to handle the actual state transition."""
        # Cancel any pending timeout
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None
        
        if self._is_speaking:
            duration = time.time() - self._speech_start_time if self._speech_start_time else None
            logger.debug(
                f"Agent stopped speaking "
                f"(utterance_id={self._utterance_id}, duration={duration:.3f}s)"
            )
        
        self._is_speaking = False
        self._utterance_id = None
        self._speech_start_time = None
    
    async def _auto_timeout_speech(self) -> None:
        """Internal coroutine for auto-timeout functionality."""
        try:
            await asyncio.sleep(self._auto_timeout)
            async with self._lock:
                if self._is_speaking:
                    logger.warning(
                        f"Auto-timeout triggered for utterance_id={self._utterance_id}. "
                        "Forcing speech stop. This may indicate an agent-side issue."
                    )
                    await self._stop_speaking_internal()
        except asyncio.CancelledError:
            # Normal cancellation when speech ends before timeout
            pass
    
    def get_state(self) -> AgentStateSnapshot:
        """
        Get current agent state snapshot (non-blocking).
        
        Returns:
            AgentStateSnapshot: Current state of the agent.
            
        Note:
            This method does NOT acquire the lock to remain non-blocking.
            For state-dependent critical decisions, use is_currently_speaking()
            or check the result within a proper async context.
        """
        current_time = time.time()
        duration = None
        
        if self._is_speaking and self._speech_start_time:
            duration = current_time - self._speech_start_time
        
        return AgentStateSnapshot(
            is_speaking=self._is_speaking,
            utterance_id=self._utterance_id,
            speech_start_time=self._speech_start_time,
            speech_duration=duration,
        )
    
    def is_currently_speaking(self) -> bool:
        """
        Quick check if agent is currently speaking (non-blocking).
        
        Returns:
            bool: True if agent is speaking, False otherwise.
            
        Note:
            Since this doesn't acquire the lock, there's a tiny race
            window where the actual state might have changed. This is
            acceptable for the use case (interruption decisions).
        """
        return self._is_speaking
    
    def get_current_utterance_id(self) -> Optional[str]:
        """
        Get the current utterance ID (non-blocking).
        
        Returns:
            Optional[str]: Current utterance ID or None if not speaking.
        """
        return self._utterance_id
    
    def get_speech_duration(self) -> Optional[float]:
        """
        Get duration of current speech in seconds (non-blocking).
        
        Returns:
            Optional[float]: Duration in seconds or None if not speaking.
        """
        if self._is_speaking and self._speech_start_time:
            return time.time() - self._speech_start_time
        return None
    
    async def reset(self) -> None:
        """
        Reset the state manager to initial state.
        
        This is useful for testing or hard resets.
        """
        async with self._lock:
            if self._timeout_task:
                self._timeout_task.cancel()
                self._timeout_task = None
            
            self._is_speaking = False
            self._utterance_id = None
            self._speech_start_time = None
            
            logger.debug("AgentStateManager reset")
    
    def __repr__(self) -> str:
        """String representation of current state."""
        state = self.get_state()
        return (
            f"AgentStateManager(is_speaking={state.is_speaking}, "
            f"utterance_id={state.utterance_id}, "
            f"duration={state.speech_duration:.3f}s)" 
            if state.speech_duration
            else f"AgentStateManager(is_speaking={state.is_speaking})"
        )
