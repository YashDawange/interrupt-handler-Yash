import asyncio
import logging
from typing import Any

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.voice.events import (
    AgentStateChangedEvent,
    SpeechCreatedEvent,
    UserInputTranscribedEvent,
    UserStateChangedEvent,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import config
from buffer import InterruptionBuffer
from interruption_handler import Decision, InterruptionHandler
from state_manager import AgentStateTracker

logger = logging.getLogger("interrupt-handler-agent")

load_dotenv()


class MyAgent(Agent):
    """Simple voice agent used to exercise the interruption handler."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful genz voice assistant. "
                "Keep responses concise and conversational. "
                "Do not use emojis or markdown."
            ),
        )

    async def on_enter(self) -> None:
        # Kick off an initial reply so we can immediately test interruptions.
        self.session.generate_reply()


class LiveKitInterruptionBuffer(InterruptionBuffer):
    """Concrete buffer that executes interruptions against an AgentSession."""

    def __init__(
        self,
        handler: InterruptionHandler,
        state_tracker: AgentStateTracker,
        session: AgentSession,
        *,
        timeout_ms: int | None = None,
    ) -> None:
        self._session = session
        super().__init__(handler, state_tracker, timeout_ms=timeout_ms)

    async def _execute_pending_locked(self) -> None:  # type: ignore[override]
        """Override to actually interrupt the LiveKit AgentSession."""

        event = self._pending_event
        self._pending_event = None

        if event is None:
            return

        decision = event.decision

        logger.debug(
            "LiveKitInterruptionBuffer: executing pending event decision=%s data=%r",
            decision.value if decision else None,
            event.event_data,
        )

        # When the agent is speaking and we have an explicit INTERRUPT decision,
        # we call session.interrupt(). RESPOND is handled by the normal LiveKit
        # pipeline once the user transcript is committed.
        if decision == Decision.INTERRUPT:
            try:
                logger.info("LiveKitInterruptionBuffer: calling session.interrupt()")
                await self._session.interrupt()
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("LiveKitInterruptionBuffer: error during interrupt()")


server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Core LiveKit agent session
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        min_interruption_words=999,
    )

    # Metrics collection (unchanged from basic example)
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage() -> None:
        summary = usage_collector.get_summary()
        logger.info("Usage summary: %s", summary)

    ctx.add_shutdown_callback(log_usage)

    # Our interruption handling components
    state_tracker = AgentStateTracker()
    handler = InterruptionHandler(state_tracker)
    buffer = LiveKitInterruptionBuffer(
        handler,
        state_tracker,
        session,
        timeout_ms=config.BUFFER_TIMEOUT_MS,
    )

    #
    # Event wiring
    #

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        # Map LiveKit's AgentState into our high-level speaking flag.
        if ev.new_state == "speaking":
            asyncio.create_task(state_tracker.set_speaking())
        elif ev.old_state == "speaking" and ev.new_state != "speaking":
            asyncio.create_task(state_tracker.set_silent())

    @session.on("speech_created")
    def _on_speech_created(ev: SpeechCreatedEvent) -> None:
        # This event corresponds to a new TTS utterance; we treat this as
        # the agent starting to speak for the purpose of our tracker.
        logger.debug("speech_created event: user_initiated=%s", ev.user_initiated)
        asyncio.create_task(state_tracker.set_speaking())

        # When the speech completes, SpeechHandle will update the agent state
        # via AgentSession internals; we rely on agent_state_changed to mark
        # silence rather than hooking speech_handle callbacks here.

    @session.on("user_state_changed")
    def _on_user_state_changed(ev: UserStateChangedEvent) -> None:
        # When the user starts speaking while the agent is speaking, this is
        # where VAD would normally trigger an interruption. Instead of
        # interrupting immediately, we queue a pending event in our buffer
        # and wait briefly for STT to confirm intent.
        if ev.new_state == "speaking" and session.agent_state == "speaking":
            logger.info(
                "User started speaking while agent is speaking; queuing potential interruption"
            )
            asyncio.create_task(
                buffer.queue_interruption(
                    {
                        "type": "user_started_speaking",
                        "created_at": ev.created_at,
                    }
                )
            )

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
        # Feed all user transcripts into the buffer so it can make a semantic
        # decision about whether to ignore or interrupt.
        logger.debug(
            "user_input_transcribed: text=%r is_final=%s", ev.transcript, ev.is_final
        )
        if ev.is_final:
            asyncio.create_task(buffer.on_stt_transcription(ev.transcript))

    # Start the realtime session using our agent
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)


