"""
Example Voice Agent with Backchanneling Filter

This example demonstrates the intelligent interruption handling using the
BackchannelingFilter with your LiveKit configuration.

Usage:
    python examples/voice_agent_with_backchanneling.py

Environment Variables Required:
    LIVEKIT_URL
    LIVEKIT_API_KEY
    LIVEKIT_API_SECRET
    OPENAI_API_KEY
    DEEPGRAM_API_KEY
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Optional dependency: python-dotenv. Fallback to a minimal loader if missing.
try:  # pragma: no cover
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover
    def load_dotenv(dotenv_path: str = ".env") -> None:
        """Minimal .env loader: key=value per line, ignores comments/blank lines."""
        if not os.path.exists(dotenv_path):
            return
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
# Make local livekit-agents importable without installing the package
REPO_ROOT = Path(__file__).resolve().parents[1]
LIVEKIT_AGENTS_PATH = REPO_ROOT / "livekit-agents"
if str(LIVEKIT_AGENTS_PATH) not in sys.path:
    sys.path.insert(0, str(LIVEKIT_AGENTS_PATH))

from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, openai, silero

# Load environment variables
load_dotenv()

logger = logging.getLogger("voice-agent")
logger.setLevel(logging.INFO)


async def entrypoint(ctx: JobContext):
    """
    Main entry point for the voice agent.
    
    The BackchannelingFilter is automatically integrated into the agent.
    When users say "yeah", "ok", or "hmm" while the agent is speaking,
    the agent will continue without interruption.
    """
    logger.info(f"Connecting to room: {ctx.room.name}")
    
    # Wait for participant to connect
    await ctx.connect()
    
    # Wait for the first participant
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant connected: {participant.identity}")
    
    # Initialize the agent session with backchanneling filter support
    agent = agents.VoiceAgent(
        # VAD (Voice Activity Detection) - Required for backchanneling filter
        vad=silero.VAD.load(),
        
        # STT (Speech-to-Text) - Deepgram
        stt=deepgram.STT(
            api_key=os.getenv("DEEPGRAM_API_KEY"),
            model="nova-2-general",
            language="en-US",
        ),
        
        # LLM (Large Language Model) - OpenAI
        llm=openai.LLM(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-mini",
        ),
        
        # TTS (Text-to-Speech) - OpenAI
        tts=openai.TTS(
            api_key=os.getenv("OPENAI_API_KEY"),
            voice="alloy",
        ),
        
        # Chat context - Initial system message
        chat_ctx=agents.ChatContext(
            messages=[
                agents.ChatMessage(
                    role="system",
                    content=(
                        "You are a helpful AI assistant demonstrating the backchanneling filter. "
                        "When explaining concepts, speak in longer paragraphs to give users a chance "
                        "to provide feedback like 'yeah', 'ok', or 'hmm' without interrupting you. "
                        "Be conversational and informative."
                    ),
                )
            ]
        ),
        
        # Interruption settings - backchanneling filter is automatically applied
        allow_interruptions=True,
        min_interruption_duration=0.5,
        min_interruption_words=0,  # No minimum words needed (filter handles this)
    )
    
    # Start the agent
    agent.start(ctx.room, participant)
    
    # Initial greeting
    await agent.say(
        "Hello! I'm a voice agent with intelligent interruption handling. "
        "I can distinguish between your feedback like 'yeah' or 'ok' and "
        "real interruptions like 'stop' or 'wait'. Try it out! "
        "I'll explain something interesting, and you can provide feedback "
        "without interrupting me."
    )
    
    logger.info("Agent started successfully with backchanneling filter enabled")
    
    # Example: Agent explains something while user can provide feedback
    await asyncio.sleep(2)
    await agent.say(
        "Let me tell you about artificial intelligence. "
        "AI is a fascinating field that has been developing for decades. "
        "It involves creating computer systems that can perform tasks that "
        "typically require human intelligence, such as visual perception, "
        "speech recognition, decision-making, and language translation. "
        "The recent advances in machine learning and neural networks have "
        "enabled AI to achieve remarkable results in many domains. "
        "You can say 'yeah' or 'ok' while I'm speaking and I won't stop!"
    )


def main():
    """Run the voice agent."""
    # Verify environment variables
    required_vars = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "OPENAI_API_KEY",
        "DEEPGRAM_API_KEY",
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file")
        return
    
    logger.info("Starting Voice Agent with Backchanneling Filter...")
    logger.info(f"LiveKit URL: {os.getenv('LIVEKIT_URL')}")
    logger.info("Backchanneling filter is automatically enabled")
    logger.info("")
    logger.info("Test Scenarios:")
    logger.info("  1. Say 'yeah', 'ok', or 'hmm' while agent is speaking → Agent continues")
    logger.info("  2. Say 'yeah' when agent is silent → Agent responds normally")
    logger.info("  3. Say 'stop' or 'wait' while agent is speaking → Agent stops immediately")
    logger.info("  4. Say 'yeah but wait' while agent is speaking → Agent stops (command detected)")
    logger.info("")
    
    # Run the agent
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
            ws_url=os.getenv("LIVEKIT_URL"),
        )
    )


if __name__ == "__main__":
    main()
