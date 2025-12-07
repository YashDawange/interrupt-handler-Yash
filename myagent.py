import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.agents.voice import BackchannelFilter
# VAD is optional - comment out if onnxruntime has DLL issues
try:
    from livekit.plugins import silero
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    print("Warning: VAD (silero) not available. Agent will work without VAD.")

# Turn detector - Using "stt" turn detection which works perfectly with backchannel filter
# MultilingualModel requires onnxruntime which has DLL issues on Windows
# The backchannel filter uses STT transcripts, so "stt" turn detection is ideal

logger = logging.getLogger("backchannel-test-agent")

load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice. "
            "With that in mind, keep your responses concise and to the point. "
            "Do not use emojis, asterisks, markdown, or other special characters in your responses. "
            "You are curious and friendly, and have a sense of humor. "
            "You will speak English to the user. "
            "When explaining something, speak in longer sentences to test the backchannel filter. "
            "For example, explain a topic in detail so the user can say 'yeah' or 'ok' while you're speaking.",
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()


server = AgentServer()


def prewarm(proc: JobProcess):
    if VAD_AVAILABLE:
        try:
            proc.userdata["vad"] = silero.VAD.load()
        except Exception as e:
            logger.warning(f"Failed to load VAD: {e}. Continuing without VAD.")
            proc.userdata["vad"] = None
    else:
        proc.userdata["vad"] = None


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Create a backchannel filter with default settings
    # You can customize the ignore_words and command_words if needed
    backchannel_filter = BackchannelFilter(
        ignore_words=[
            "yeah",
            "ok",
            "okay",
            "hmm",
            "hmmm",
            "right",
            "uh-huh",
            "uh huh",
            "aha",
            "mhm",
            "mm-hmm",
            "mm hmm",
            "yep",
            "yup",
            "sure",
            "got it",
            "gotcha",
            "alright",
            "all right",
        ],
        command_words=[
            "wait",
            "stop",
            "no",
            "hold on",
            "pause",
            "cancel",
            "nevermind",
            "never mind",
            "don't",
            "dont",
            "not",
            "wrong",
            "incorrect",
        ],
    )

    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears
        stt="deepgram/nova-3",
        # A Large Language Model (LLM) is your agent's brain
        llm="openai/gpt-4.1-mini",
        # Text-to-speech (TTS) is your agent's voice
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # VAD and turn detection (both are optional)
        # Using "stt" turn detection - works perfectly with backchannel filter
        turn_detection="stt",
        vad=ctx.proc.userdata.get("vad"),
        # Enable preemptive generation for better responsiveness
        preemptive_generation=True,
        # Resume false interruptions
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        # Enable the backchannel filter
        backchannel_filter=backchannel_filter,
    )

    # Log metrics as they are emitted
    from livekit.agents import metrics, MetricsCollectedEvent

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)
