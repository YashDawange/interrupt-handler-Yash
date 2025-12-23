import logging
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
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from backchanneling_handling_service import (
    BackchannelingHandlingService,
    BackchannelingConfig,
)

logger = logging.getLogger("basic-agent")
load_dotenv()

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Alita. "
                "You are a general-purpose conversational voice assistant. "
                "You can talk about any topic the user wants, ask follow-up questions, "
                "explain concepts clearly, and help with reasoning or problem solving. "
                "Keep your responses concise, natural, and suitable for spoken conversation. "
                "Do not use emojis, markdown, bullet points, or special formatting. "
                "Speak clearly in a friendly, calm, and engaging tone. "
                "You may ask clarifying questions when needed."
            ),
        )

    async def on_enter(self):
        self.session.generate_reply()

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="google/gemini-2.0-flash-lite",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,

        allow_interruptions=False,
        discard_audio_if_uninterruptible=False,

    )
    #Attaching the backchanneling handling service to this session
    BackchannelingHandlingService(
        session=session,
        config=BackchannelingConfig(),
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
    )

if __name__ == "__main__":
    cli.run_app(server)