import logging
import re
from dotenv import load_dotenv
from google.genai.types import Modality  # noqa: F401

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, room_io
from livekit.agents.llm import function_tool
from livekit.plugins import google, openai  # noqa: F401

logger = logging.getLogger("realtime-with-tts")
logger.setLevel(logging.INFO)

load_dotenv()

# --- INTERRUPT LOGIC ADDED ---
IGNORE_WORDS = {"yeah", "ok", "okay", "hmm", "uh-huh", "right"}
INTERRUPT_WORDS = {"stop", "wait", "hold on", "no"}

# agent speaking state
agent_is_speaking = False


def classify_user_text(text: str, is_speaking: bool):
    """
    Returns:
        "ignore"      -> ignore input completely
        "interrupt"   -> stop agent immediately
        "process"     -> handle normally
    """

    text_clean = text.lower().strip()

    # Agent is speaking → check interruption rules
    if is_speaking:

        # exact ignore word ("yeah", "ok")
        if text_clean in IGNORE_WORDS:
            return "ignore"

        # mixed sentence interruption ("yeah wait", "ok stop")
        for w in INTERRUPT_WORDS:
            if w in text_clean:
                return "interrupt"

        # backchannel or short phrase while speaking → ignore
        if len(text_clean.split()) <= 3:
            return "ignore"

        return "ignore"

    # Agent is silent → treat all as normal input
    return "process"


# This example follows the default LiveKit pipeline.
class WeatherAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are a helpful assistant.",
            llm=openai.realtime.RealtimeModel(modalities=["text"]),
            tts=openai.TTS(voice="ash"),
        )

    # --- OVERRIDE HOOKS TO TRACK SPEAKING STATE ---
    async def on_tts_started(self, *args, **kwargs):
        global agent_is_speaking
        agent_is_speaking = True
        logger.info("TTS started → agent_is_speaking = True")

    async def on_tts_finished(self, *args, **kwargs):
        global agent_is_speaking
        agent_is_speaking = False
        logger.info("TTS finished → agent_is_speaking = False")

    # --- THIS IS THE CORE INTERRUPTION LOGIC ---
    async def on_text(self, text, ctx):
        global agent_is_speaking

        behavior = classify_user_text(text, agent_is_speaking)

        if behavior == "ignore":
            logger.info(f"IGNORED while speaking: {text}")
            return

        if behavior == "interrupt":
            logger.info(f"INTERRUPTED by user: {text}")
            await self.interrupt()  # stop agent TTS immediately
            return await super().on_text(text, ctx)

        # normal processing
        logger.info(f"Processed input: {text}")
        return await super().on_text(text, ctx)

    # ------------------------------------------------------------------

    @function_tool
    async def get_weather(self, location: str):
        logger.info(f"getting weather for {location}")
        return f"The weather in {location} is sunny, and the temperature is 20 degrees Celsius."


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession()

    await session.start(
        agent=WeatherAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            text_output=True,
            audio_output=True,
        ),
    )
    session.generate_reply(instructions="say hello to the user in English")


if __name__ == "__main__":
    cli.run_app(server)
