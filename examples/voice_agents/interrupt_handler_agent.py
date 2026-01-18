import asyncio
import logging
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    room_io,
)
from livekit.plugins import silero, deepgram, openai

load_dotenv()
logger = logging.getLogger("interrupt-handler-agent")

class InterruptHandlerAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are a helpful assistant. You should ignore backchanneling words like 'yeah', 'ok', 'hmm' while you are speaking, but respond to them if you are silent.",
        )

    async def on_enter(self):
        self.session.generate_reply()

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(),
        tts=openai.TTS(),
        vad=ctx.proc.userdata["vad"],
        interruption_speech_filter=["yeah", "ok", "hmm", "uh-huh", "right"],
        resume_false_interruption=True,
    )

    await session.start(agent=InterruptHandlerAgent(), room=ctx.room)

if __name__ == "__main__":
    cli.run_app(server)
