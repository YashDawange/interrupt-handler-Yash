import asyncio
import os
import logging
import time
from typing import Optional

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, google, silero, cartesia

from config import AgentConfig
from utils import Logger, UtteranceTracker
from dialogue import SpeechIntentClassifier, TurnManager, TurnStrategy, UserIntent

# Configure logging
logging.basicConfig(level=logging.INFO)

async def entrypoint(ctx: JobContext):
    """
    Main agent entrypoint.
    """
    # Load config and init helpers
    config = AgentConfig.from_env()
    logger = Logger("smart-agent")
    
    tracker = UtteranceTracker(config.transcript_buffer_size, config.duplicate_window_seconds)
    classifier = SpeechIntentClassifier()
    turn_manager = TurnManager(config, logger)

    await ctx.connect()
    logger.log_action("CONNECTED", f"Room: {ctx.room.name}")

    # Initialize plugins
    # Note: Ensure these env vars are set
    llm = google.LLM(model=os.getenv("GOOGLE_LLM_MODEL", "gemini-2.5-flash"))
    stt = deepgram.STT(model=os.getenv("DEEPGRAM_MODEL", "nova-3"))
    tts = cartesia.TTS()
    vad = silero.VAD.load()

    # Define the agent
    agent = Agent(
        instructions=(
            "You are a helpful and conversational voice assistant. "
            "You are currently testing a new interruption handling system. "
            "If the user says 'yeah', 'ok', or 'hmm' while you are speaking, ignore it and keep talking. "
            "If they say 'stop' or ask a question, stop and respond. "
            "Keep your responses concise and natural."
        )
    )

    # Initialize session
    # CRITICAL: allow_interruptions=False globally to prevent VAD from automatically pausing the agent.
    # We will handle interruptions manually in the logic layer.
    # AND we must set discard_audio_if_uninterruptible=False so STT still works!
    session = AgentSession(
        vad=vad,
        stt=stt,
        llm=llm,
        tts=tts,
        allow_interruptions=False, 
        discard_audio_if_uninterruptible=False,
        turn_detection="vad",
    )

    # State tracking
    agent_is_speaking = False
    is_processing_reply = False
    last_interrupt_time = 0.0

    @session.on("agent_state_changed")
    def on_agent_state(ev):
        nonlocal agent_is_speaking, is_processing_reply
        new_state = getattr(ev, "new_state", None)
        logger.log_action("STATE_CHANGE", f"New state: {new_state}")
        
        if new_state == "speaking":
            agent_is_speaking = True
        elif new_state == "listening":
            agent_is_speaking = False
            is_processing_reply = False

    @session.on("user_input_transcribed")
    def on_user_input(ev):
        # Run async logic
        asyncio.create_task(handle_user_input(ev))

    async def handle_user_input(ev):
        nonlocal is_processing_reply, last_interrupt_time
        
        # Extract text
        text = ""
        if hasattr(ev, "user_transcript") and ev.user_transcript:
            text = ev.user_transcript
        elif hasattr(ev, "alternatives") and ev.alternatives:
            text = ev.alternatives[0].text
        
        if not text:
            return

        is_final = getattr(ev, "is_final", True) # Default to true if missing
        
        # Deduplication
        if tracker.is_duplicate(text):
            return
        tracker.add(text)

        logger.log_input(text, is_final, "speaking" if agent_is_speaking else "listening")

        # Classification
        intent = classifier.classify(text)
        logger.log_classification(text, intent.value)

        # Strategy
        time_since_interrupt = time.time() - last_interrupt_time
        # Treat "processing reply" as speaking so we can interrupt it too
        effective_speaking_state = agent_is_speaking or is_processing_reply
        strategy = turn_manager.decide_strategy(intent, effective_speaking_state, is_final, time_since_interrupt)

        if strategy == TurnStrategy.IGNORE:
            # Do nothing, let agent keep talking
            return

        elif strategy == TurnStrategy.INTERRUPT:
            # Stop immediately
            logger.log_action("INTERRUPT", "Stopping audio")
            last_interrupt_time = time.time()
            await session.interrupt(force=True)
            # Ensure we don't accidentally trigger a reply if one was pending or if the "Stop" is processed as a turn
            is_processing_reply = False 
            return

        elif strategy == TurnStrategy.INTERRUPT_AND_RESPOND:
            # Stop and generate reply
            logger.log_action("INTERRUPT_AND_RESPOND", "Stopping and replying")
            last_interrupt_time = time.time()
            await session.interrupt(force=True)
            # Small delay to let audio clear
            await asyncio.sleep(config.interrupt_settle_delay_seconds)
            
            if not is_processing_reply:
                is_processing_reply = True
                # CRITICAL: allow_interruptions=False to prevent self-interruption or VAD stutter
                session.generate_reply(user_input=text, allow_interruptions=False)
            return

        elif strategy == TurnStrategy.RESPOND:
            # Normal turn-taking
            if not is_processing_reply:
                logger.log_action("RESPOND", "Generating reply")
                is_processing_reply = True
                session.generate_reply(user_input=text, allow_interruptions=False)
            return
            
        elif strategy == TurnStrategy.WAIT:
            # Wait for more context (interim results)
            return

    # Start the session
    await session.start(agent=agent, room=ctx.room)
    
    # Initial greeting
    logger.log_action("GREETING", "Sending initial greeting")
    # allow_interruptions=False ensures we don't stop if user coughs or says "hey" immediately
    session.say("Hello! I am your context-aware assistant. You can interrupt me, or just say 'yeah' to show you're listening.", allow_interruptions=False)

def main():
    # Force load from current directory and override any shell vars
    load_dotenv(dotenv_path=".env", override=True)
    # Ensure keys exist
    keys = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "DEEPGRAM_API_KEY", "GOOGLE_API_KEY", "CARTESIA_API_KEY"]
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        print(f"Missing env vars: {missing}")
        return
    
    print(f"DEBUG: LIVEKIT_URL is set to: {os.getenv('LIVEKIT_URL')}")


    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

if __name__ == "__main__":
    main()
