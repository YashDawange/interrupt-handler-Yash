import logging

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.plugins import cartesia, deepgram, openai, silero

logger = logging.getLogger("interrupt-handler-agent")

load_dotenv()

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        vad=silero.VAD.load(),
        llm=openai.LLM(model="gpt-4o-mini"),
        stt=deepgram.STT(),
        tts=cartesia.TTS(),
        # Configure filler words that won't interrupt when agent is speaking
        filler_words=['yeah', 'ok', 'hmm', 'right', 'uh-huh', 'aha', 'okay', 'alright', 'sure', 'yep'],
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
    )

    await session.start(agent=Agent(instructions="You are a helpful assistant that can be interrupted by commands but ignores filler words like 'yeah' or 'ok' when speaking."), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)