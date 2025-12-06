import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero, assemblyai, groq, deepgram
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from examples.voice_agents.salescode_assignment.backchannel_handle import InterruptionHandler

logger = logging.getLogger("basic-agent")

load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is kelly. You interact with users via voice. "
                "Keep your responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or other special characters "
                "in your responses. "
                "You are curious and friendly, and have a sense of humor. "
                "You will speak English to the user."
            ),
        )

    async def on_enter(self):
        self.session.generate_reply(
            instructions="Greet the user briefly."
        )



server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        # models
        stt=assemblyai.STT(),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts = deepgram.TTS(),   
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],

        preemptive_generation=True,
        allow_interruptions=False,        
        discard_audio_if_uninterruptible=False,
        false_interruption_timeout=None,  
        resume_false_interruption=False,
    )

    InterruptionHandler(session=session).attach()

    # metrics
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
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
