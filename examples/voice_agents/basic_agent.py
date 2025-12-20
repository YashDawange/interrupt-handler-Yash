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

IGNORE WORDS = {
    "ah", "aha", "hmm", "uh", "um", "mm",
    "mhm", "mhmm", "mmhmm", "uh-huh",

    "ok", "okay", "alright", "sure",
    "yeah", "yep", "yes",

    "oh", "wow", "nice", "cool",
    "really", "right", "exactly",

    "got", "it", "i", "see",
    "makes", "sense", "understood",

    "go", "on"
}


class DemoAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "Your name is Kelly. You would interact with users via voice."
            "with that in mind keep your responses concise and to the point."
            "do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "you will speak english to the user"
            )
        )

    async def on_enter(self):
        
        self.session.generate_reply()

server = AgentServer()

def prewarm(proc):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="google/gemini-2.5-flash",   
        tts="cartesia/sonic-2",
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),

      
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
