"""
Intelligent Interruption Agent for LiveKit

This agent demonstrates the Temporal-Semantic Fusion (TSF) approach for handling
user interruptions. It ignores backchanneling ("yeah", "ok") while speaking but
responds to active commands ("stop", "wait").

Usage:
    python agent.py dev     # Development mode with hot reload
    python agent.py console # Terminal testing mode
    python agent.py start   # Production mode

Environment Variables:
    - LIVEKIT_URL: LiveKit server URL
    - LIVEKIT_API_KEY: API key for authentication
    - LIVEKIT_API_SECRET: API secret for authentication
    - DEEPGRAM_API_KEY: Deepgram STT API key
    - OPENAI_API_KEY: OpenAI LLM/TTS API key
    - IGNORE_WORDS: (Optional) Comma-separated list of backchannel words to ignore
"""

import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.plugins import silero, openai, deepgram

# Import the modular interruption handler
from interruption_handler import setup_interruption_handler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("intelligent-interruption-agent")

load_dotenv()


class IntelligentAgent(Agent):
    """
    A demonstration agent that explains a topic while handling interruptions intelligently.
    
    - Ignores backchanneling words ("yeah", "ok", "hmm") while speaking
    - Responds to commands ("stop", "wait") immediately
    - Treats all input as valid when silent
    """
    
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful assistant demonstrating intelligent interruption handling. "
                "Speak in long, flowing sentences to showcase the seamless handling of backchannels. "
                "If the user says 'stop' or 'wait', acknowledge that you were interrupted. "
                "If the user says 'yeah' or 'ok' while you are silent, treat it as confirmation."
            ),
        )

    async def on_enter(self):
        """Called when the agent enters the session. Start with a demo explanation."""
        await self.session.say(
            "Hello! I am demonstrating intelligent interruption handling. "
            "While I am speaking, you can say 'yeah', 'ok', or 'hmm' to show you are listening, "
            "and I will continue without stopping. "
            "However, if you say 'stop' or 'wait', I will pause immediately. "
            "Let me tell you about the history of the Roman Empire. "
            "The Roman Empire was one of the largest empires in ancient history, "
            "spanning from Britain in the north to Egypt in the south, "
            "and from Spain in the west to Mesopotamia in the east. "
            "It lasted for over a thousand years and left an indelible mark on Western civilization.",
            allow_interruptions=False  # Disable VAD auto-interruption; we handle it manually
        )


# Initialize the server
server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm function to load VAD model before sessions start."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model prewarmed")


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for each RTC session.
    
    Sets up the AgentSession with:
    - Deepgram STT for speech-to-text
    - OpenAI LLM for conversation
    - OpenAI TTS for text-to-speech
    - Silero VAD for voice activity detection
    - Intelligent Interruption Handler for backchannel filtering
    """
    ctx.log_context_fields = {"room": ctx.room.name}
    
    # Create the AgentSession with all components
    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(),
        tts=openai.TTS(),
        vad=ctx.proc.userdata["vad"],
    )
    
    # Set up the intelligent interruption handler
    # This registers the user_input_transcribed event handler
    handler = setup_interruption_handler(session)
    
    # Log when backchannels are ignored vs interruptions triggered
    handler.on_backchannel = lambda text: logger.info(f"Backchannel ignored: '{text}'")
    handler.on_interrupt = lambda text: logger.info(f"Interrupt triggered: '{text}'")
    
    # Create and register the agent
    agent = IntelligentAgent()
    server.register_agent(agent)
    
    # Start the session
    await session.start(agent)
    
    logger.info(f"Session started for room: {ctx.room.name}")


if __name__ == "__main__":
    cli.run_app(server)
