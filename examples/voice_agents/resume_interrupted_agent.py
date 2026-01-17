import os
import asyncio
import logging
from dotenv import load_dotenv

from livekit.agents import AgentServer, AgentSession, JobContext, cli, Agent
from livekit.plugins import deepgram, openai, silero
from livekit.agents.voice.room_io import RoomInputOptions

from interrupt_handler import InterruptHandler

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

server = AgentServer()


class DummyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are inactive. All logic handled externally."
        )


@server.rtc_session()
async def entrypoint(ctx: JobContext):

    session = AgentSession(
        vad=silero.VAD.load(),

        llm=openai.LLM(
            model="llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1"
        ),

        stt=deepgram.STT(),
        tts=deepgram.TTS(),
    )

    handler = InterruptHandler(session)

    # Only listen to FINAL transcripts
    @session.stt.on("transcript")
    def on_transcript(ev):
        if not ev.is_final:
            return
        if not ev.text:
            return

        asyncio.create_task(handler.handle(ev.text))

    await session.start(
        agent=DummyAgent(),
        room=ctx.room,

        # Disable built-in turn-taking completely
        room_input_options=RoomInputOptions(
            text_input_cb=lambda *_: None,
            close_on_disconnect=True
        )
    )


if __name__ == "__main__":
    cli.run_app(server)
