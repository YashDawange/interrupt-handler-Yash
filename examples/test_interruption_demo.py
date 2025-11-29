import logging

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, openai, silero, cartesia

# Enable debug logging to see interruption decisions
logging.basicConfig(level=logging.DEBUG)


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    agent = Agent(
        instructions=(
            "You are a test assistant. When the user asks you to explain something, give a long and detailed that takes at least 20-30 seconds to speak. Talk slowly and include many details. If the user just says 'yeah', 'ok', 'hmm', 'uh-huh' or 'right' "
            "don't treat it as an interrupt and continue your current explanation without stopping. "
            "Only stop if they say 'stop', 'wait', 'no' or ask a real question."
        ),
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(),
        min_interruption_duration=0.5,
        min_interruption_words=0,
        false_interruption_timeout=2.0,
        resume_false_interruption=True,
    )

    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(
        instructions="Greet the user."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

