# myagent.py

from dotenv import load_dotenv

load_dotenv()

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import deepgram, elevenlabs, openai, silero

from interrupt_handler import ContextAwareSTT


@function_tool
async def lookup_weather(
    context: RunContext,
    location: str,
):
    """Used to look up weather information."""
    return {"weather": "sunny", "temperature": 70}


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    agent = Agent(
        instructions="You are a friendly voice assistant built by LiveKit.",
        tools=[lookup_weather],
    )

    # Base STT engine
    stt_instance = deepgram.STT(model="nova-3")

    # Wrap with our context-aware interruption handler
    context_aware_stt = ContextAwareSTT(stt_instance)

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=context_aware_stt,
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=elevenlabs.TTS(),
        # tts=openai.TTS(),

        # Let the user interrupt, but our logic decides WHEN it actually matters
        allow_interruptions=True,

        # Tuned so short “ok / yeah” don’t count as real interruptions
        # (we handle them in our wrapper)
        min_interruption_words=2,         # need >= 2 words to count as a “real” interruption
        false_interruption_timeout=0.15,  # quickly resume on false interruptions
        resume_false_interruption=True,
    )

    # Give our wrapper access to session events
    context_aware_stt.set_session(session)

    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(
        instructions="Greet the user naturally and ask about their day."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
