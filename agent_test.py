from livekit.plugins import deepgram, openai, silero
from livekit.agents import Agent, AgentSession, JobContext, cli, WorkerOptions

# renamed function import (compat alias still exists in the module)
from interruption import attach_interruption_filter

async def main_entry(ctx: JobContext) -> None:
    voice_agent = Agent(
        instructions=(
            "You are a friendly voice assistant. "
            "Keep answers short and conversational."
        ),
        tools=[],
    )

    convo = AgentSession(
        vad=silero.VAD.load(),
        # These names are looked up by LiveKit Inference using your LIVEKIT_* env vars
        stt="deepgram/nova-3",          # STT model
        llm="openai/gpt-4.1-mini",      # or "openai/gpt-4o-mini"
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",  # example voice

        # Let LiveKit generate transcripts while speaking
        allow_interruptions=True,
        # tiny one-word things become 'false' interruptions that can resume
        min_interruption_words=2,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    # 🔑 Attach our interruption logic (renamed entry)
    attach_interruption_filter(convo)

    await convo.start(agent=voice_agent, room=ctx.room)

    await convo.generate_reply(
        instructions="Greet the user and ask how you can help."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=main_entry))
