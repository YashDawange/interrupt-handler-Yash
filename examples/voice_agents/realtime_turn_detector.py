import logging

from intelligent_interrupt_handler import IntelligentInterruptHandler

from dotenv import load_dotenv

from google.genai import types  # noqa: F401

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, JobProcess, cli
from livekit.plugins import deepgram, google, openai, silero  # noqa: F401
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("realtime-turn-detector")
logger.setLevel(logging.INFO)

load_dotenv()

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        allow_interruptions=False,   # IMPORTANT: disable default interruptions
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=openai.realtime.RealtimeModel(
            voice="alloy",
            turn_detection=None,
            input_audio_transcription=None,
        ),
    )

    interrupt_handler = IntelligentInterruptHandler(stt_wait_ms=250)

    agent = Agent(instructions="You are a helpful assistant.")
    await session.start(agent=agent, room=ctx.room)

    # --- Hook STT final transcript into handler ---
    @session.on("user_transcript_final")
    def _on_user_transcript_final(msg):
        interrupt_handler.notify_transcript(msg.text)

    # --- Hook VAD trigger (user starts speaking) ---
    @session.on("user_started_speaking")
    async def _on_user_started_speaking():
        decision = await interrupt_handler.decide()
        print(f"[INTERRUPT_DECISION] speaking={interrupt_handler.agent_speaking} decision={decision}")

        if decision == "IGNORE":
            return

        if decision == "INTERRUPT":
            await session.interrupt()
            return

    # --- Demo greet ---
    interrupt_handler.set_agent_speaking(True)
    await session.say("Hello! I am ready. Tell me what you want to learn today.")
    interrupt_handler.set_agent_speaking(False)


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm

if __name__ == "__main__":
    cli.run_app(server)
