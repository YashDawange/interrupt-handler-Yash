"""Example agent demonstrating backchanneling detection.

This agent shows how backchanneling detection works to filter passive
acknowledgements (like "yeah", "ok", "hmm") when the agent is speaking,
while still allowing active interruptions (like "wait", "stop", "no").
"""

import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    cli,
    room_io,
)
from livekit.plugins import deepgram, groq, silero

logger = logging.getLogger("backchanneling-agent")

# Enable debug logging to see what's happening
logging.basicConfig(level=logging.INFO)

load_dotenv()


class BackchannelingDemoAgent(Agent):
    """Agent that demonstrates backchanneling detection."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful assistant named Alex. "
                "You speak clearly and provide detailed explanations. "
                "When explaining something, you tend to give longer, more detailed responses. "
                "Keep your responses conversational and natural. "
                "Do not use emojis, asterisks, markdown, or other special characters."
            )
        )

    async def on_enter(self):
        """Called when the agent enters the session."""
        logger.info("Agent entered session, generating greeting...")
        # Generate an initial greeting
        handle = self.session.generate_reply(
            instructions="Greet the user warmly and introduce yourself as Alex. Ask how you can help them today."
        )
        logger.info(f"Greeting handle created: {handle}")


server = AgentServer()


def prewarm(proc):
    """Preload VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Entry point for the agent session."""
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Create session with backchanneling detection enabled
    # You can customize the filler and interruption words if needed
    # Using direct plugin instances instead of string names to avoid LiveKit gateway
    # Using Groq LLM (free tier) and Deepgram TTS (same API key as STT) instead of OpenAI to avoid quota issues
    # If you have OpenAI quota, you can switch back to: openai.LLM(model="gpt-4o-mini") and openai.TTS(voice="alloy")
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),  # Groq free tier
        tts=deepgram.TTS(),  # Deepgram TTS (uses same DEEPGRAM_API_KEY as STT)
        vad=ctx.proc.userdata["vad"],
        turn_detection="vad",
        # Enable backchanneling detection (enabled by default)
        backchanneling_enabled=True,
        # Optionally customize filler words
        # backchanneling_filler_words=["yeah", "ok", "hmm", "right", "uh-huh"],
        # Optionally customize interruption words
        # backchanneling_interruption_words=["wait", "stop", "no", "hold on"],
        # Enable resume on false interruption for smoother experience
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    await session.start(
        agent=BackchannelingDemoAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(server)
