import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    cli,
    room_io,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("interrupt-demo")
load_dotenv()

IGNORE_WORDS = [
    "absolutely", "ah", "aha", "alright", "cool",
    "exactly", "go", "on", "got", "it", "hmm", "i", "see",
    "makes", "sense", "mhm", "mhmm", "mm", "hmm", "mmhmm",
    "nice", "oh", "ok", "okay", "really", "right", "sure",
    "uh", "uh-huh", "um", "understood", "wow", "yeah",
    "yep", "yes"
]

class DemoAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are explaining something continuously. "
                "If the user gives short acknowledgements like yeah or hmm, keep talking. "
                "If the user says stop or wait, stop immediately."
            )
        )

    async def on_enter(self):
        # Start speaking immediately (important for demos)
        self.session.generate_reply()

server = AgentServer()

def prewarm(proc):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="google/gemini-2.5-flash",   # or openai/gpt-4o-mini
        tts="cartesia/sonic-2",
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),

        # 🔑 THESE 5 LINES ARE THE SOLUTION
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        interrupt_ignore_words=IGNORE_WORDS,
        min_interruption_words=0,
    )

    await session.start(
        agent=DemoAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )

if __name__ == "__main__":
    cli.run_app(server)
