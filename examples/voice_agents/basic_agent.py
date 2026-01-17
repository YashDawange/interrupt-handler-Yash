import logging
import os
import re
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
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# --------------------------------------------------
# Setup
# --------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

# --------------------------------------------------
# Configurable filler words (can be changed easily)
# --------------------------------------------------
DEFAULT_FILLERS = [
    "hmm", "hm", "uh", "uhh", "yeah", "yea",
    "ok", "okay", "oh", "right", "mm"
]

FILLER_WORDS = os.getenv(
    "IGNORED_WORDS",
    ",".join(DEFAULT_FILLERS)
).split(",")

FILLER_REGEX = re.compile(
    r"^(" + "|".join(w.strip() for w in FILLER_WORDS) + r")+$",
    re.IGNORECASE,
)


def is_filler(text: str) -> bool:
    if not text:
        return False
    return bool(FILLER_REGEX.match(text.strip()))


# --------------------------------------------------
# Agent with mediator logic
# --------------------------------------------------
class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. "
                "You speak clearly and naturally. "
                "Do not use emojis or special formatting."
            )
        )

        self.agent_speaking = False

    async def on_enter(self):
        self.agent_speaking = True
        self.session.generate_reply()

    async def on_agent_speech_start(self):
        self.agent_speaking = True

    async def on_agent_speech_end(self):
        self.agent_speaking = False

    async def on_user_transcript(self, text: str):
        logger.info(f"user: {text}")

        # -------- MEDIATOR DECISION LAYER --------

        # Case 1: Agent is speaking + filler word → IGNORE
        if self.agent_speaking and is_filler(text):
            logger.info("mediator: filler ignored while agent speaking")
            return

        # Case 2: Agent is idle + filler → VALID turn
        if not self.agent_speaking and is_filler(text):
            logger.info("mediator: filler accepted while agent idle")
            self.session.generate_reply()
            return

        # Case 3: Meaningful input → interrupt & respond
        logger.info("mediator: meaningful input")
        self.agent_speaking = True
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self,
        context: RunContext,
        location: str,
        latitude: str,
        longitude: str,
    ):
        return "It is sunny today with a pleasant temperature."


# --------------------------------------------------
# Server setup
# --------------------------------------------------
server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


# --------------------------------------------------
# Job entrypoint
# --------------------------------------------------
@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

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

    usage = metrics.UsageCollector()

    @session.on("metrics_collected")
    def on_metrics(ev: MetricsCollectedEvent):
        usage.collect(ev.metrics)

    async def log_usage():
        logger.info(f"usage: {usage.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(server)
