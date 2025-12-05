"""
Example demonstrating the backchannel filter feature.

This example shows how to configure the agent to ignore backchannel
acknowledgments (like "yeah", "ok", "hmm") when the agent is speaking,
while still allowing real interruption commands (like "stop", "wait") to work.
"""

import logging

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.plugins import cartesia, deepgram, openai, silero

logger = logging.getLogger("backchannel-filter-agent")

load_dotenv()

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        vad=silero.VAD.load(),
        llm=openai.LLM(model="gpt-4o-mini"),
        stt=deepgram.STT(),
        tts=cartesia.TTS(),
        # Enable backchannel filter (default is True)
        enable_backchannel_filter=True,
        # Optionally customize the list of backchannel words
        # If not provided, uses a default comprehensive list
        backchannel_words=[
            "yeah",
            "ok",
            "okay",
            "hmm",
            "uh-huh",
            "mhm",
            "right",
            "sure",
            "yep",
            "got it",
            "i see",
        ],
        # Existing false interruption handling still works
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
    )

    await session.start(
        agent=Agent(
            instructions="You are a helpful assistant. Speak naturally and wait for the user to finish speaking before responding."
        ),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)

