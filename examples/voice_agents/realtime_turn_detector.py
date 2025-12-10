import logging
from dotenv import load_dotenv
from google.genai import types
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, JobProcess, cli
from livekit.plugins import deepgram, google, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("realtime-turn-detector")
logger.setLevel(logging.INFO)

load_dotenv()

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        allow_interruptions=False,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=openai.realtime.RealtimeModel(
            voice="alloy",
            turn_detection=None,
            input_audio_transcription=None,
        ),
    )

    await session.start(
        agent=Agent(instructions="You are a helpful assistant."),
        room=ctx.room,
    )

    agent_speaking = False

    IGNORE_WORDS = {"yeah", "okay", "hmm", "uh", "uh-huh", "right", "mm", "mhm", "ok"}
    STOP_WORDS = {"stop", "wait", "no", "hold", "cancel", "pause"}

    @session.event_handler("assistant_speech_started")
    async def on_assistant_speech_started(ev):
        nonlocal agent_speaking
        agent_speaking = True

    @session.event_handler("assistant_speech_finished")
    async def on_assistant_speech_finished(ev):
        nonlocal agent_speaking
        agent_speaking = False

    @session.event_handler("transcription")
    async def on_transcription(ev):
        nonlocal agent_speaking

        text = ev.text
        if not text:
            return

        text_lower = text.lower().strip()
        raw_words = text_lower.split()
        words = {w.strip(".,?!:;-—'\"") for w in raw_words if w.strip(".,?!:;-—'\"")}

        has_stop_word = bool(words & STOP_WORDS)
        only_ignore_words = words and words.issubset(IGNORE_WORDS)

        if has_stop_word:
            if agent_speaking:
                await session.stop_output()
                agent_speaking = False
            await session.input_text(text)
            return

        if only_ignore_words and agent_speaking:
            return

        if only_ignore_words and not agent_speaking:
            await session.input_text(text)
            return

        if agent_speaking:
            await session.stop_output()
            agent_speaking = False
        await session.input_text(text)
        return 


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm

if __name__ == "__main__":
    cli.run_app(server)
