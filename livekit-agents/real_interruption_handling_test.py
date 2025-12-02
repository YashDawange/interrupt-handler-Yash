#!/usr/bin/env python3

import asyncio
import logging
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.agents.voice.interruption_filter import InterruptionFilter
from livekit.plugins import openai, deepgram, elevenlabs

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def entrypoint(ctx: agents.JobContext):
    """Test agent with intelligent interruption handling."""

    logger.info("🤖 Starting interruption test agent...")

    await ctx.connect()

    # Create custom interruption filter for testing
    interruption_filter = InterruptionFilter(
        # Add some test-specific words
        backchannel_words={
            "yeah",
            "ok",
            "okay",
            "hmm",
            "alright",
            "uh-huh",
            "right",
            "mhm",
            "gotcha",
            "okay, got it",
            "understood",
            "i see",
            "uh",
            "um",
            "mm",
            "got it",
            "sure",
            "yep",
            "yes",
            "absolutely",
            "definitely",
            "roger that",
            "make sense",
        },
        interruption_words={"wait", "stop", "hold on", "pause", "no", "actually"},
    )

    # Create agent session with interruption filter
    session = AgentSession(
        stt=deepgram.STT(
            model="nova-2",
            language="en", 
            smart_format=True,
            interim_results=True,  # Essential for real-time interruption detection
        ),
        llm=openai.LLM(
            model="gpt-4o-mini",
            temperature=0.7,
        ),
        tts=openai.TTS(
            voice="nova",  # OpenAI voices: alloy, echo, fable, onyx, nova, shimmer
            speed=1.0,
        ),
        # Disable the conflicting feature
        resume_false_interruption=False,
        # llm=openai.realtime.RealtimeModel(
        #     voice="coral",
        #     temperature=0.7,
        # ),
        interruption_filter=interruption_filter,  # Add our custom filter
        # room_input_options=RoomInputOptions(
        #     # auto_subscription=True,
        #     auto_track_subscription=True
        # )
        
        min_interruption_duration=0.3,   # Minimum duration before interruption
        min_interruption_words=1,        # Minimum words to trigger interruption (will be overridden by our filter)
    )

    # Define test agent with specific behaviors
    agent_instructions = """
    You are a test assistant designed to help validate interruption handling.
    
    When the user says:
    - "tell me a long story" - speak continuously for 30+ seconds about any topic
    - "count slowly" - count from 1 to 20 with 2-second pauses between numbers
    - "describe something" - give a detailed 45+ second description of any object
    - "explain a concept" - provide a lengthy explanation of a technical concept
    
    Be conversational and engaging. When interrupted, acknowledge the interruption politely.
    """

    await session.start(room=ctx.room, agent=Agent(instructions=agent_instructions))

    # Initial greeting with test instructions
    await session.generate_reply(
        instructions="""
        Greet the user and say:
        "Hello! I'm your interruption test agent. You can ask me to:
        - Tell me a long story
        - Count slowly  
        - Describe something
        - Explain a concept
        
        Try saying backchannel words like 'yeah', 'ok', 'hmm' while I'm speaking - I should continue.
        Try interrupting with 'wait', 'stop', or 'hold on' - I should pause immediately.
        What would you like to test first?"
        """
    )

    logger.info("✅ Agent started successfully with interruption handling!")


if __name__ == "__main__":
    # Configure agent options
    worker_options = agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        # Add any additional worker configuration here
    )

    # Start the agent
    agents.cli.run_app(worker_options)
