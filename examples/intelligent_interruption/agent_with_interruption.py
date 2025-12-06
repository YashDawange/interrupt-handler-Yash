"""
Agent with Intelligent Interruption Handling

This example demonstrates how to implement intelligent interruption handling that
distinguishes between backchanneling (yeah, ok, hmm) and real interruptions (stop, wait, no)
based on whether the agent is currently speaking.
"""

import logging
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AgentStateChangedEvent,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    UserInputTranscribedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from interruption_handler import IntelligentInterruptionHandler

if TYPE_CHECKING:
    from livekit.agents.voice.agent_activity import AgentActivity

logger = logging.getLogger("intelligent-interruption-agent")

load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You are a helpful voice assistant. "
                "When explaining something, you can be detailed and thorough. "
                "Keep your responses natural and conversational. "
                "Do not use emojis, asterisks, markdown, or other special characters in your responses."
            ),
        )

    async def on_enter(self):
        # Generate an initial greeting
        self.session.generate_reply(
            instructions="Greet the user warmly and ask how you can help them today."
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Initialize the intelligent interruption handler
    interruption_handler = IntelligentInterruptionHandler()

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    # Track agent speaking state
    def on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        is_speaking = ev.new_state == "speaking"
        interruption_handler.set_agent_speaking(is_speaking)
        logger.debug(f"Agent state changed: {ev.new_state} (speaking: {is_speaking})")

    session.on("agent_state_changed", on_agent_state_changed)

    # Store current transcript for interruption checking
    # This will be used when VAD triggers before STT provides transcript
    current_user_transcript = {"text": ""}

    def on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
        # Update current transcript
        current_user_transcript["text"] = ev.transcript
        logger.debug(f"User transcript: '{ev.transcript}' (final: {ev.is_final})")

    session.on("user_input_transcribed", on_user_input_transcribed)

    # Start the session
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )

    # Monkey-patch the _interrupt_by_audio_activity method to add our filtering logic
    # This is done after session.start() because that's when _activity is created
    activity: "AgentActivity" = session._activity  # type: ignore

    # Store the original method
    original_interrupt = activity._interrupt_by_audio_activity

    def patched_interrupt_by_audio_activity() -> None:
        """Patched version that checks interruption handler before interrupting."""
        # Get the current transcript from audio recognition
        transcript = ""
        if activity._audio_recognition is not None:
            transcript = activity._audio_recognition.current_transcript
            # If no transcript yet, use the last transcribed text
            if not transcript:
                transcript = current_user_transcript["text"]

        # If we have a transcript and agent is speaking, check if we should ignore
        if transcript and interruption_handler._agent_is_speaking:
            if interruption_handler.should_ignore_interruption(transcript):
                logger.info(
                    f"Ignoring interruption: '{transcript}' (agent is speaking, "
                    "detected as backchanneling)"
                )
                return  # Don't interrupt - agent continues speaking
            else:
                logger.info(
                    f"Allowing interruption: '{transcript}' "
                    "(agent is speaking, but contains command words)"
                )
        elif not transcript and interruption_handler._agent_is_speaking:
            # VAD triggered but no transcript yet - be conservative and allow interruption
            # This handles the case where VAD is faster than STT
            # Better to interrupt than to miss a real command
            logger.debug(
                "VAD triggered interruption before STT transcript available - allowing "
                "to be safe"
            )
        elif transcript:
            # Agent is not speaking, process normally
            logger.debug(f"Processing user input: '{transcript}' (agent is silent)")

        # Call the original method to perform the interruption
        original_interrupt()

    # Replace the method
    activity._interrupt_by_audio_activity = patched_interrupt_by_audio_activity

    logger.info("Intelligent interruption handler installed")

    # Log metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)


if __name__ == "__main__":
    cli.run_app(server)

