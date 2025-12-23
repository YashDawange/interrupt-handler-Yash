import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, JobProcess, cli
from livekit.plugins import cartesia, deepgram, google, silero

logger = logging.getLogger("intelligent-interrupt")
logger.setLevel(logging.INFO)

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

SOFT_WORDS = [
    "yeah",
    "yep",
    "yes",
    "ok",
    "okay",
    "uh huh",
    "mm hmm",
    "mhm",
    "right",
    "sure",
    "hmm",
    "aha",
    "uh",
    "um",
    "got it",
]

STOP_COMMANDS = [
    "stop",
    "wait",
    "hold on",
    "hang on",
    "pause",
    "no",
    "cancel",
]

CORRECTION_CUES = [
    "actually",
    "correction",
    "no that's wrong",
    "no it is",
    "not quite",
    "instead",
]


class GuideAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a concise, friendly voice guide. Keep responses short and natural. "
                "Do not use markdown or emojis. Acknowledge quick answers like 'yeah' when "
                "you are listening, but ignore them when you are already talking."
            ),
        )

    async def on_enter(self):
        await self.session.generate_reply(instructions="Greet the user briefly and offer help.")


server = AgentServer()

DISPATCH_AGENT_NAME = os.getenv("INTERRUPT_AGENT_NAME", "intelligent-interrupt")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name=DISPATCH_AGENT_NAME)
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-3-flash-preview"),
        tts=cartesia.TTS(),
        # Enable semantic interruption handling: ignore backchanneling while speaking,
        # but still interrupt immediately on real commands ("stop", "wait", ...).
        semantic_interruption_soft_words=SOFT_WORDS,
        semantic_interruption_stop_commands=STOP_COMMANDS,
        semantic_interruption_correction_cues=CORRECTION_CUES,
    )

    await session.start(agent=GuideAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)

