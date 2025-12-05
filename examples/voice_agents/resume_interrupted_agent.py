import logging
from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.plugins import cartesia, deepgram, openai, silero
from livekit.plugins import cartesia, deepgram, google, silero

logger = logging.getLogger("resume-agent")


async def entrypoint(ctx: JobContext):
    session = AgentSession(
        vad=silero.VAD.load(),
        llm=openai.LLM(model="gpt-4o-mini"),
        llm="google/gemini-2.5-flash-lite",
        stt=deepgram.STT(),
        tts=cartesia.TTS(),
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
    )
    await session.start(agent=Agent(instructions="You are a helpful assistant."), room=ctx.room)
if __name__ == "__main__":
    cli.run_app(server)