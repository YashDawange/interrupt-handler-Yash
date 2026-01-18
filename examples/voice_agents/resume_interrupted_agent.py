import asyncio
import logging
import os
import re

from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.agents.voice.room_io import RoomInputOptions
from livekit.plugins import silero, deepgram, cartesia, openai

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("semantic-interrupt-agent")

server = AgentServer()

IGNORE_WORDS = {
    "uh", "um", "hmm", "hm", "yeah", "yes", "yep",
    "okay", "ok", "uhh", "mmm", "right"
}

STOP_WORDS = {
    "stop", "wait", "pause", "cancel", "hold", "no"
}


def normalize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z\s]", "", text)
    return text.split()


def contains_stop(words: list[str]) -> bool:
    return any(w in STOP_WORDS for w in words)


def all_ignore(words: list[str]) -> bool:
    return bool(words) and all(w in IGNORE_WORDS for w in words)


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        vad=silero.VAD.load(),
        llm=openai.LLM(
            model="llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        ),
        stt=deepgram.STT(),
        tts=cartesia.TTS(),
    )

    agent = Agent(instructions="You are a helpful assistant.")

    current_task: asyncio.Task | None = None
    lock = asyncio.Lock()
    agent_speaking = False

    async def speak(text: str):
        nonlocal current_task, agent_speaking
        async with lock:
            agent_speaking = True
            current_task = asyncio.create_task(session.say(text))
            try:
                await current_task
            finally:
                current_task = None
                agent_speaking = False

    async def interrupt():
        nonlocal current_task, agent_speaking
        async with lock:
            if current_task:
                current_task.cancel()
            current_task = None
            agent_speaking = False

    @session.stt.on("transcript")
    def on_transcript(ev):
        if not ev.is_final or not ev.text:
            return

        words = normalize(ev.text)
        if not words:
            return

        async def handle():
            # STOP always wins
            if contains_stop(words):
                logger.info(f"INTERRUPT: {ev.text}")
                await interrupt()
                return

            # Agent speaking
            if agent_speaking:
                if all_ignore(words):
                    logger.info(f"IGNORED filler while speaking: {ev.text}")
                else:
                    logger.info(f"IGNORED non-stop speech while speaking: {ev.text}")
                return

            # Agent silent
            if all_ignore(words):
                logger.info(f"VALID short answer: {ev.text}")
                await speak("Okay, starting now.")
                return

            await speak(ev.text)

        asyncio.create_task(handle())

    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            text_input_cb=lambda *_: None,
            close_on_disconnect=True,
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
