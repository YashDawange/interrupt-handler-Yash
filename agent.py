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

# Print where the modules are being imported from
print("=" * 80)
print("📍 Module Import Locations")
print("=" * 80)

import livekit.agents
import livekit.agents.voice
print(f"livekit.agents: {livekit.agents.__file__}")
print(f"livekit.agents.voice: {livekit.agents.voice.__file__}")

print(f"\nPlugins:")
print(f"  groq: {groq.__file__}")
print(f"  cartesia: {cartesia.__file__}")
print(f"  deepgram: {deepgram.__file__}")
print(f"  silero: {silero.__file__}")

# Find the voice_assistant.py file location
import os
voice_dir = os.path.dirname(livekit.agents.voice.__file__)
voice_assistant_path = os.path.join(voice_dir, "voice_assistant.py")
print(f"\n🎯 Voice Assistant file location:")
print(f"  {voice_assistant_path}")
print(f"  Exists: {os.path.exists(voice_assistant_path)}")

print("=" * 80 + "\n")

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    
    agent = Agent(
        instructions="You are a friendly voice assistant. Explain things clearly and thoroughly.",
    )
    
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=cartesia.TTS(),
    )
    
    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(
        instructions="Greet the user and offer to explain any topic they're interested in."
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
