from livekit.plugins import groq, cartesia, deepgram, silero
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from dotenv import load_dotenv


load_dotenv()

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    
    agent = Agent(
        instructions="You are a friendly voice assistant. Explain things clearly and thoroughly.",
    )
    
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2"),
       llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=cartesia.TTS(),  # Changed this line
    )
    
    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(
        instructions="Greet the user and offer to explain any topic they're interested in."
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))