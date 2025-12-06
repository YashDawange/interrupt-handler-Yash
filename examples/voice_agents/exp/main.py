# main.py

import logging
import sys
import re
from pathlib import Path
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
    cli,
    metrics,
    room_io,
    UserInputTranscribedEvent,
)
from livekit.plugins import silero, google
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from interrupt_handler import HandlingInterrupt
if TYPE_CHECKING:
    from livekit.agents.voice.agent_activity import AgentActivity

logger = logging.getLogger("simple-interrupt-agent")
load_dotenv()

COMMAND_REGEX = re.compile(
    r"\b(stop|wait|pause|hold on|hold)\b",
    re.IGNORECASE,
)


class MyAgent(Agent):
    """
    A simple voice agent with a fixed persona and a startup greeting.
    """
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You are a helpful voice assistant. "
                "When explaining something, you can be detailed and thorough, "
                "but keep responses natural and conversational. "
                "Do not use emojis, asterisks, markdown, or other special characters. "
                "If the user says small backchannel words like 'yeah', 'ok', 'hmm', "
                "while you are speaking, you should continue your answer as if "
                "you didn't hear them."
            ),
        )

    async def on_enter(self):
        self.session.generate_reply(
            instructions=(
                "Greet the user warmly and ask how you can help them today. "
                "Keep it short."
            )
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    """Pre-warm VAD model before the first user connects."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    agent_speaking = {"value": False}

    session = AgentSession(
        stt="deepgram/nova-3",
        llm=google.LLM(model="gemini-2.0-flash"),
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=False,
        false_interruption_timeout=1.0,
    )

    def on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        """
        A simple event listener to keep track of the agent's speaking state.
        """
        is_speaking = ev.new_state == "speaking"
        agent_speaking["value"] = is_speaking
        logger.debug(
            f"Agent state changed: {ev.new_state} (speaking={is_speaking})"
        )

    session.on("agent_state_changed", on_agent_state_changed)

    def on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
        text = ev.transcript or ""
        logger.debug(
            f"User transcript: '{ev.transcript}' (final={ev.is_final})"
        )

        if not text:
            return

        if COMMAND_REGEX.search(text):
            logger.info(
                f"[HARD INTERRUPT] Detected command in: '{text}' "
                f"(agent_speaking={agent_speaking['value']})"
            )
            session.interrupt()
            return

    session.on("user_input_transcribed", on_user_input_transcribed)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )

    logger.info("Simple hard-interrupt handler installed")

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        """Log final usage summary on shutdown."""
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)


if __name__ == "__main__":
    cli.run_app(server)
