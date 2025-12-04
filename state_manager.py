import asyncio
import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """High-level speaking state of the agent."""

    SPEAKING = "speaking"
    SILENT = "silent"
    TRANSITIONING = "transitioning"


class AgentStateTracker:
    """Tracks whether the agent is currently speaking or silent.

    This is updated from TTS start/stop hooks so that interruption
    decisions can be conditioned on whether the agent is talking.
    """

    def __init__(self) -> None:
        self._current_state: AgentState = AgentState.SILENT
        self._speaking_start_time: Optional[float] = None
        self._lock = asyncio.Lock()

    def get_state(self) -> AgentState:
        """Return the current agent state."""
        return self._current_state

    def is_speaking(self) -> bool:
        """Return True if the agent is currently speaking."""
        return self._current_state == AgentState.SPEAKING

    async def set_speaking(self) -> None:
        """Mark the agent as speaking. Call when TTS starts playing."""
        async with self._lock:
            self._current_state = AgentState.SPEAKING
            self._speaking_start_time = time.time()
            logger.debug(
                "Agent state changed to SPEAKING at %.3f", self._speaking_start_time
            )

    async def set_silent(self) -> None:
        """Mark the agent as silent. Call when TTS finishes."""
        async with self._lock:
            prev_state = self._current_state
            self._current_state = AgentState.SILENT
            end_time = time.time()
            start_time = self._speaking_start_time
            self._speaking_start_time = None

            if start_time is not None:
                duration = end_time - start_time
                logger.debug(
                    "Agent state changed from %s to SILENT, spoke for %.3f seconds",
                    prev_state.value,
                    duration,
                )
            else:
                logger.debug("Agent state changed from %s to SILENT", prev_state.value)


