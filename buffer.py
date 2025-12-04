import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import config
from interruption_handler import Decision, InterruptionHandler
from state_manager import AgentStateTracker

logger = logging.getLogger(__name__)


@dataclass
class InterruptionEvent:
    """Represents a potential interruption triggered by VAD."""

    timestamp: float
    agent_state_when_queued: str
    event_data: dict[str, Any]
    stt_text: Optional[str] = None
    decision: Optional[Decision] = None
    


class InterruptionBuffer:
    """Buffers VAD-triggered interruptions until STT confirms intent.

    VAD is fast but doesn't know what was said; STT is slower but semantic.
    This buffer waits up to BUFFER_TIMEOUT_MS for STT text to arrive, then
    uses InterruptionHandler to decide whether to ignore or execute the
    interruption.
    """

    def __init__(
        self,
        handler: InterruptionHandler,
        state_tracker: AgentStateTracker,
        *,
        timeout_ms: int | None = None,
    ) -> None:
        self._handler = handler
        self._state_tracker = state_tracker
        self._timeout = (timeout_ms or config.BUFFER_TIMEOUT_MS) / 1000.0
        self._pending_event: Optional[InterruptionEvent] = None
        self._lock = asyncio.Lock()

    async def queue_interruption(self, event_data: dict[str, Any]) -> None:
        """Queue a new VAD-triggered potential interruption.

        This should be called from the VAD callback instead of
        immediately interrupting the agent.
        """

        now = time.time()
        async with self._lock:
            self._pending_event = InterruptionEvent(
                timestamp=now,
                event_data=event_data,
                agent_state_when_queued=self._state_tracker.get_state().value,
            )

        logger.info(
            "InterruptionBuffer: queued VAD interruption at %.3f (state=%s)",
            now,
            self._state_tracker.get_state().value,
        )

        try:
            await asyncio.wait_for(self._wait_for_stt(), timeout=self._timeout)
        except asyncio.TimeoutError:
            await self._handle_timeout()

    async def _wait_for_stt(self) -> None:
        """Wait until STT text has been attached to the pending event."""

        # Simple polling; STT callback will set stt_text
        while True:
            async with self._lock:
                if self._pending_event is None:
                    # Event was resolved or cancelled
                    return
                if self._pending_event.stt_text:
                    # STT arrived; decision will be handled from STT callback
                    return
            await asyncio.sleep(0.01)  # 10ms poll

    async def on_stt_transcription(self, text: str) -> None:
        """Called when STT provides transcription for the current user speech."""

        async with self._lock:
            if self._pending_event is None:
                # No pending interruption; nothing to do
                logger.debug(
                    "InterruptionBuffer: received STT with no pending event: %r", text
                )
                return

            # Attach text and run the decision engine
            self._pending_event.stt_text = text

        logger.info("InterruptionBuffer: STT received for pending event: %r", text)

        decision, reason = self._handler.analyze_input(text, self._pending_event.agent_state_when_queued)

        async with self._lock:
            if self._pending_event is None:
                return

            self._pending_event.decision = decision

            if decision == Decision.IGNORE:
                logger.info(
                    "InterruptionBuffer: cancelling interruption (decision=IGNORE, reason=%s)",
                    reason,
                )
                self._pending_event = None
                return

            logger.info(
                "InterruptionBuffer: executing interruption (decision=%s, reason=%s)",
                decision.value,
                reason,
            )
            await self._execute_pending_locked()

    async def _handle_timeout(self) -> None:
        """Handle buffer timeout with configurable fallback behavior."""

        async with self._lock:
            if self._pending_event is None:
                return

            event = self._pending_event

        logger.warning(
            "InterruptionBuffer: timeout waiting for STT (age=%.3fs, state=%s)",
            time.time() - event.timestamp,
            self._state_tracker.get_state().value,
        )

        # Decide fallback based on config and current state
        if self._state_tracker.is_speaking():
            if config.TIMEOUT_FALLBACK is config.TimeoutFallback.IGNORE:
                logger.info(
                    "InterruptionBuffer: timeout fallback IGNORE while speaking; "
                    "keeping agent audio uninterrupted"
                )
                async with self._lock:
                    self._pending_event = None
                return

        # Default or explicit INTERRUPT fallback
        logger.info(
            "InterruptionBuffer: timeout fallback INTERRUPT; executing pending interruption"
        )
        async with self._lock:
            if self._pending_event is None:
                return
            await self._execute_pending_locked()

    async def _execute_pending_locked(self) -> None:
        """Execute the pending interruption.

        This method must be called with _lock held.
        Actual integration with LiveKit (e.g. calling session.interrupt()
        or committing a user turn) should be added by the caller via
        callbacks or by extending this class.
        """

        event = self._pending_event
        self._pending_event = None

        if event is None:
            return

        # NOTE: The concrete behavior (e.g., interrupting the AgentSession)
        # is intentionally left as a hook. For now we just log; the agent
        # integration can inspect event.event_data and event.decision and
        # perform the appropriate LiveKit calls.
        logger.debug(
            "InterruptionBuffer: _execute_pending_locked event=%r decision=%s",
            event,
            event.decision.value if event.decision else None,
        )


