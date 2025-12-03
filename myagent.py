from dotenv import load_dotenv

# load variables from .env (OPENAI_API_KEY, DEEPGRAM_API_KEY, LIVEKIT_*, etc.)
load_dotenv()

import sys
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import deepgram, openai, silero


@function_tool
async def lookup_weather(
    context: RunContext,
    location: str,
):
    """
    Simple demo tool: pretend to look up weather.
    In a real app, you would call a real API here.
    """
    return {
        "location": location,
        "weather": "sunny",
        "temperature_c": 30,
    }


async def entrypoint(ctx: JobContext):
    print("entrypoint: connecting to LiveKit...")
    await ctx.connect()
    print("entrypoint: connected. creating agent & session...")

    # LLM agent with a tool
    agent = Agent(
        instructions=(
            "You are a friendly voice assistant built by LiveKit. "
            "Greet the user, talk naturally, and you can call the "
            "`lookup_weather` tool when the user asks about weather."
        ),
        tools=[lookup_weather],
    )

    # Realtime voice session: Silero VAD, Deepgram STT, OpenAI LLM + TTS
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o"),
        tts=openai.TTS(voice="alloy"),
    )

    print("entrypoint: starting session...")
    await session.start(agent=agent, room=ctx.room)
    print("entrypoint: session started. sending initial greeting...")
    await session.generate_reply(
        instructions="Greet the user and ask how their day is going."
    )
    print("entrypoint: initial reply generated.")


if __name__ == "__main__":
    print("myagent.py starting, argv:", sys.argv)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
