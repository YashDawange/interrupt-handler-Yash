# livekit_agents/event_hooks.py
"""
Integration hooks for VAD, STT, and TTS events.
This file wires the real-time events to the Switchable InterruptionManager.
"""
import asyncio
import logging
from .interruption_manager import InterruptionManager
from .state_observer import AgentStateObserver
from .config import STT_CONFIRM_DELAY, STT_MAX_WAIT

# Configure logging for visibility into decision making
log = logging.getLogger("interrupt_hooks")
log.setLevel(logging.INFO) # Set to DEBUG for verbose output

# --- SINGLETONS ---
state = AgentStateObserver()
# The manager is instantiated once and automatically loads its mode (RULES, LLM, RAG, HYBRID)
manager = InterruptionManager() 

# --- STATE VARIABLES ---
# Tracks the last transcript received for correlation with VAD events
_last_stt_for_vad = None
_last_decision = None
_vad_lock = asyncio.Lock() # Ensures VAD and STT processing doesn't overlap

# =====================================================================
# 1. TTS LIFECYCLE HOOKS
# These must be called by your agent's TTS/Audio playback code.
# =====================================================================

async def on_tts_start():
    """Called when the agent begins speaking."""
    log.debug("AGENT_STATE: Speaking started.")
    state.on_speaking_start()

async def on_tts_end():
    """Called when the agent finishes speaking."""
    log.debug("AGENT_STATE: Speaking ended.")
    state.on_speaking_end()

# =====================================================================
# 2. VAD HOOK
# Called when VAD suggests the agent should stop talking (user spoke).
# =====================================================================

async def vad_stop_event_handler(vad_event_id: str, stop_callback: callable):
    """
    Delays the VAD stop event to allow STT time to confirm the intent.
    
    :param vad_event_id: A correlation ID for the VAD event.
    :param stop_callback: The function to call to stop the agent's TTS stream.
    """
    global _last_stt_for_vad, _last_decision
    
    async with _vad_lock:
        # Wait a small buffer time for the STT transcript to arrive
        await asyncio.sleep(STT_CONFIRM_DELAY)
        
        if _last_stt_for_vad:
            # Analyze the received transcript using the configured engine
            decision = await manager.analyze(_last_stt_for_vad, state.is_speaking())
            _last_decision = decision
            
            log.debug(f"VAD Stop Check: STT='{_last_stt_for_vad}' | Decision={decision}")
            
            if decision == "IGNORE" and state.is_speaking():
                # Case 1: Agent speaking + User said "yeah/ok" -> IGNORE
                log.info("VAD: Canceling stop due to IGNORE decision (Backchannel).")
                return # Do nothing, agent continues speaking

            if decision == "INTERRUPT" and state.is_speaking():
                # Case 2: Agent speaking + User said "stop/wait" -> INTERRUPT
                log.info("VAD: Honoring interrupt -> Stopping TTS.")
                await stop_callback() # Stop the agent's speaking
                return

        # Case 3: Default Stop (Agent silent, or no STT, or NORMAL decision)
        # If the agent is silent, VAD stop just confirms the user is done speaking.
        log.debug("VAD: No context or NORMAL decision -> Honoring stop.")
        await stop_callback()

# =====================================================================
# 3. STT HOOK
# Called on every partial or final transcript received from STT.
# =====================================================================

async def on_stt_partial(transcript: str):
    """
    Handles incoming STT transcripts. Provides immediate interrupt if detected mid-speech.
    """
    global _last_stt_for_vad, _last_decision
    _last_stt_for_vad = transcript # Update state for VAD handler
    
    if state.is_speaking():
        # Agent is speaking: we check for hard interrupts
        decision = await manager.analyze(transcript, True)
        _last_decision = decision
        
        if decision == "INTERRUPT":
            # Hard stop detected immediately (e.g., user says "STOP!")
            log.info(f"STT: Hard Interrupt detected mid-speech: '{transcript}'. Stopping immediately.")
            await _stop_tts_immediately()
            # Pass the transcript to the intent handler for processing
            await _handle_user_intent(transcript)
        # IGNORE case is handled by the VAD_STOP_EVENT_HANDLER
    
    else:
        # Agent is silent: all transcripts are potential user input.
        # We still run manager.analyze() to see if it's an IGNORE (noise/filler), 
        # but the decision logic is typically simpler when silent (rules should default to NORMAL).
        decision = await manager.analyze(transcript, False)
        
        # Original request check: if silent, must check the thing is not ignorable.
        if decision != "IGNORE" and transcript.strip():
            log.info(f"STT: Agent silent, processing user input: '{transcript}'")        
            await _handle_user_intent(transcript)
        else:
            log.debug(f"STT: Agent silent, input ignored (likely noise/empty): '{transcript}'")


# =====================================================================
# 4. PLACEHOLDERS (Must be implemented in your LiveKit Agent class)
# =====================================================================

async def _stop_tts_immediately():
    """
    MOCK FUNCTION: Replace with your actual TTS stopping mechanism.
    This function should forcefully stop the agent's current audio playback queue.
    """
    # Example implementation might involve calling a method on a TtsStream object:
    # await agent.tts_stream.stop_playback() 
    log.warning("--- TTS STOP MOCK: Agent audio stopped immediately. ---")

async def _handle_user_intent(text: str):
    """
    MOCK FUNCTION: Replace with your actual user intent processing logic.
    This is where the agent's core NLP/LLM pipeline takes over.
    
    :param text: The transcript (usually a final transcript) to process.
    """
    # Example implementation might submit a prompt to the LLM:
    # response = await llm_chain.ainvoke({"user_input": text})
    # await agent.say(response)
    log.warning(f"--- INTENT HANDLER MOCK: Processing intent for: '{text}' ---")