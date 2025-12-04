"""
Smart Interruption Test Agent

A minimal example showing how to use the smart interruption filter.
"""

import logging

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, JobContext, cli
from livekit.agents.voice.smart_session import SmartInterruptionAgentSession
from livekit.plugins import google, silero, deepgram

logger = logging.getLogger("smart-agent")
logger.setLevel(logging.INFO)

load_dotenv()


class VoiceAgent(Agent):
    """General-purpose voice agent with smart interruption support."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful voice assistant. "
                "Respond naturally to user requests. "
                "Keep your responses concise and conversational. "
                "Wait for the user to speak first before responding."
            ),
        )


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """
    Entrypoint using SmartInterruptionAgentSession.

    This demonstrates the minimal changes needed to add smart interruption
    filtering to your existing agent.
    """

    # Use SmartInterruptionAgentSession with Deepgram TTS (no quota limits)
    session = SmartInterruptionAgentSession(
        stt="deepgram/nova-3",
        llm="google/gemini-2.0-flash",
        tts=deepgram.TTS(model="aura-2-andromeda-en"),
        vad=silero.VAD.load(),
        # Smart interruption is enabled by default with sensible defaults
        smart_interruption_enabled=True,
    )

    await session.start(agent=VoiceAgent(), room=ctx.room)
    logger.info(f"Agent started in room {ctx.room.name}")


if __name__ == "__main__":
    cli.run_app(server)
