"""
Example: Intelligent Interruption Handling Demo

This example demonstrates the intelligent interruption handling feature
that can differentiate between filler words and real commands.

Test Scenarios:
1. Agent speaking + user says "yeah" → No interruption (continue speaking)
2. Agent speaking + user says "stop" → Interrupt immediately
3. Agent speaking + user says "yeah but wait" → Interrupt (mixed input)
4. Agent silent + user says "yeah" → Process as normal input
"""

import asyncio
import logging
import os

from livekit import agents, rtc
from livekit.agents import voice
from livekit.agents.llm import ChatContext, ChatMessage
from livekit.plugins import deepgram, openai, silero

# Configure logging to see interruption handler messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("interruption-demo")


async def entrypoint(ctx: agents.JobContext):
    """Main entry point for the voice agent with intelligent interruption handling."""

    logger.info("Starting intelligent interruption handling demo")

    # Initialize the agent session with interruption handling enabled
    agent_session = voice.AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="alloy"),
        vad=silero.VAD.load(),
        # Enable interruptions - the intelligent handler will manage them
        allow_interruptions=True,
        # Small delay to allow for intelligent analysis
        min_interruption_duration=0.3,
        min_interruption_words=0,  # Let the handler decide
    )

    # Create the agent with initial instructions
    agent = voice.Agent(
        instructions="""You are a helpful voice assistant demonstrating intelligent interruption handling.
        
When asked to demonstrate interruption scenarios, explain what you're about to say clearly,
then speak for about 10-15 seconds so the user can test interrupting you.

Example responses:
- "Let me tell you about the weather today. It's a beautiful sunny day with clear blue skies..."
- "I'll count from 1 to 20 slowly. One... two... three... four..."
- "Here's a detailed explanation of how our system works. First, we process the audio..."

Be conversational and natural. Respond to user commands appropriately.""",
        chat_ctx=ChatContext(),
    )

    # Start the session
    await ctx.connect()
    session_run = agent_session.start(ctx.room, agent)

    # Log session start
    logger.info("Agent session started - ready for interruption testing")

    # Add event listeners to demonstrate interruption handling
    @agent_session.on("user_input_transcribed")
    def on_user_transcript(event: voice.UserInputTranscribedEvent):
        if event.is_final:
            logger.info(f"User said (final): {event.transcript}")
        else:
            logger.debug(f"User said (interim): {event.transcript}")

    @agent_session.on("agent_state_changed")
    def on_agent_state_changed(event: voice.AgentStateChangedEvent):
        logger.info(f"Agent state: {event.old_state} → {event.new_state}")

    @agent_session.on("speech_created")
    def on_speech_created(event: voice.SpeechCreatedEvent):
        logger.info(
            f"Agent speech created (interruptible: {event.speech_handle.allow_interruptions})"
        )

    # Initial greeting
    await agent_session.say(
        """Hello! I'm demonstrating intelligent interruption handling. 
        
Try these test scenarios:
1. While I'm speaking, say just "yeah" or "ok" - I should keep talking
2. While I'm speaking, say "stop" or "wait" - I should stop immediately
3. While I'm speaking, say "yeah but wait" - I should stop
4. When I'm quiet, say "yeah" - I'll respond to it normally

What would you like me to do?"""
    )

    await session_run


def main():
    """Run the demo worker."""
    logger.info("Intelligent Interruption Handling Demo")
    logger.info("=" * 60)
    logger.info("Configuration:")
    logger.info(f"  LIVEKIT_IGNORE_WORDS: {os.getenv('LIVEKIT_IGNORE_WORDS', 'default')}")
    logger.info(f"  LIVEKIT_COMMAND_WORDS: {os.getenv('LIVEKIT_COMMAND_WORDS', 'default')}")
    logger.info("=" * 60)

    worker = agents.Worker(entrypoint=entrypoint)
    agents.run_app(worker)


if __name__ == "__main__":
    main()
