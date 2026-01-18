from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import openai, silero


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    agent = Agent(instructions="You are a helpful voice assistant.")
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=openai.STT(model="whisper-1"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="alloy"),
    )

    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(instructions="greet the user")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
