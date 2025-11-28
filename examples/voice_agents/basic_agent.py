import logging
import multiprocessing
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
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

multiprocessing.freeze_support()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

load_dotenv()

INTERRUPT_WORDS = {"stop", "wait", "pause", "cancel", "no", "hold on"}
BACKCHANNELS = {"yeah", "ok", "okay", "mhm", "hmm", "right", "alright", "mm"}


class MyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are Kelly, a friendly AI assistant. "
                "Keep responses natural and concise. "
                "Do not use emojis."
            )
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(self, ctx, location: str, latitude: str, longitude: str):
        logger.info(f"Looking up weather for {location}")
        return "It is sunny and warm."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
        allow_interruptions=False,
        preemptive_generation=True,
    )

    session.userdata["backchannels"] = 0

    usage = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _metrics(ev: MetricsCollectedEvent):
        usage.collect(ev.metrics)

    @session.on("transcription")
    async def handle_input(text: str, lang: str):
        user = text.lower().strip()
        count = session.userdata["backchannels"]

        # Interruption
        if any(w in user for w in INTERRUPT_WORDS):
            session.stop_speaking()
            session.userdata["backchannels"] = 0
            await session.generate_response("Okay. What would you like instead?")
            return

        # Backchannel filter
        if user in BACKCHANNELS:
            session.userdata["backchannels"] = count + 1
            print(f"[Ignored filler: {user}]")
            return

        # Real message
        session.userdata["backchannels"] = 0
        print(f"[User Intent: {user}]")

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
