import asyncio
import logging

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import silero

# Enable debug logging for the interruption arbiter
logging.getLogger("livekit.agents.voice.interruptions").setLevel(logging.DEBUG)


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    agent = Agent(
        instructions="You are a helpful assistant. When asked, give a long explanation about any topic."
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        # Explicitly configure interruption filtering
        interruption_ignore_phrases=["yeah", "ok", "okay", "hmm", "uh huh", "right"],
        interruption_command_phrases=["stop", "wait", "hold on", "no"],
        interruption_false_start_delay=0.15,
    )

    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(
        instructions="Give a very long, detailed explanation about the history of computers. Keep talking for at least 30 seconds."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
