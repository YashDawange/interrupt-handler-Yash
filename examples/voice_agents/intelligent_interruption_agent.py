"""
Example agent demonstrating intelligent interruption handling.

"""
import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    cli,
    llm,
    metrics,
    room_io,
    stt,
    tts,
    vad,
)
from livekit.plugins import silero

logger = logging.getLogger("intelligent-interruption-agent")
logger.setLevel(logging.INFO)

load_dotenv()


class IntelligentInterruptionAgent(Agent):
    """Agent with intelligent interruption handling enabled automatically."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful assistant that explains things clearly and concisely. "
                "When explaining something, continue speaking even if the user says "
                "'yeah', 'ok', or 'hmm' - these are just acknowledgements. "
                "However, if the user says 'stop', 'wait', or 'no', you should stop immediately. "
                "Keep your responses natural and conversational."
            )
        )

    async def on_enter(self):
        """Called when the agent is added to the session."""
        # The agent will generate a reply according to its instructions
        self.session.generate_reply()


server = AgentServer()


def prewarm(proc):
    """Prewarm VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Entrypoint for the intelligent interruption agent."""
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Create session with standard STT, LLM, and TTS
    # The intelligent interruption handler is automatically enabled
    session = AgentSession(
        # Speech-to-text (STT) - converts user speech to text
        stt="deepgram/nova-3",
        # Large Language Model (LLM) - processes input and generates responses
        llm="openai/gpt-4.1-mini",
        # Text-to-speech (TTS) - converts text to speech
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # Voice Activity Detection (VAD) - detects when user is speaking
        vad=ctx.proc.userdata["vad"],
        # Allow preemptive generation for faster responses
        preemptive_generation=True,
        # Resume false interruptions (handled by intelligent interruption handler)
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

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

    # Start the session with our agent
    await session.start(
        agent=IntelligentInterruptionAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)

