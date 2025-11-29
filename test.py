from livekit.plugins import deepgram, elevenlabs, openai, silero
from livekit.agents import Agent, AgentSession, JobContext, cli, WorkerOptions

# import the function we just defined
from interruption_handler import install_interruption_handler  # if you put it in another file
# or if it's in the same file, just call install_interruption_handler directly
from dotenv import load_dotenv
load_dotenv()

async def entrypoint(ctx: JobContext) -> None:
    agent = Agent(
        instructions=(
            "You are a friendly voice assistant. "
            "Keep answers short and conversational."
        ),
        tools=[],
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        # These names are looked up by LiveKit Inference using your LIVEKIT_* env vars
        stt="deepgram/nova-3",          # STT model
        llm="openai/gpt-4.1-mini",      # or "openai/gpt-4o-mini" if that’s what the task says
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",  # example voice


        # Let LiveKit generate transcripts while speaking
        allow_interruptions=True,
        # tiny one-word things become 'false' interruptions that can resume
        min_interruption_words=2,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    # 🔑 Attach our interruption logic
    install_interruption_handler(session)

    await session.start(agent=agent, room=ctx.room)

    await session.generate_reply(
        instructions="Greet the user and ask how you can help."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
