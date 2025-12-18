# livekit_agents/event_hooks.py
"""
Integration hooks for VAD, STT, and TTS events.
This file wires the real-time events to the Switchable InterruptionManager.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from .interruption_manager import InterruptionManager
from .state_observer import AgentStateObserver
from .config import STT_CONFIRM_DELAY, STT_MAX_WAIT

# Configure logging
log = logging.getLogger("interrupt_hooks")
log.setLevel(logging.INFO)

# --- SINGLETONS ---
state = AgentStateObserver()
manager = InterruptionManager() 

# --- STATE VARIABLES ---
_last_stt_for_vad = None
_last_decision = None
_vad_lock = asyncio.Lock()
_stt_timestamp = None
_agent_start_time = None
_user_start_time = None

# Reference to TTS stream (will be set by agent)
_tts_stream = None
_intent_handler = None

# =====================================================================
# SETUP FUNCTIONS - Call these from your agent initialization
# =====================================================================

def set_tts_stream(tts_stream):
    """Set the TTS stream reference for stopping playback."""
    global _tts_stream
    _tts_stream = tts_stream
    log.info("TTS stream reference set.")

def set_intent_handler(handler):
    """Set the intent handler callback for processing user input."""
    global _intent_handler
    _intent_handler = handler
    log.info("Intent handler set.")

# =====================================================================
# 1. TTS LIFECYCLE HOOKS
# =====================================================================

async def on_tts_start():
    """Called when the agent begins speaking."""
    global _agent_start_time
    _agent_start_time = datetime.now().timestamp() * 1000  # Convert to ms
    state.on_speaking_start()
    log.debug(f"AGENT_STATE: Speaking started at {_agent_start_time}ms")

async def on_tts_end():
    """Called when the agent finishes speaking."""
    global _agent_start_time
    state.on_speaking_end()
    _agent_start_time = None
    log.debug("AGENT_STATE: Speaking ended.")

# =====================================================================
# 2. VAD HOOK - Enhanced with audio metadata
# =====================================================================

async def vad_stop_event_handler(
    vad_event_id: str, 
    stop_callback: callable,
    audio_rms: float = 0.0,
    vad_confidence: float = 1.0
):
    """
    Delays the VAD stop event to allow STT time to confirm the intent.
    
    :param vad_event_id: Correlation ID for the VAD event
    :param stop_callback: Function to call to stop the agent's TTS stream
    :param audio_rms: RMS energy of the audio signal
    :param vad_confidence: VAD confidence score (0-1)
    """
    global _last_stt_for_vad, _last_decision, _user_start_time, _agent_start_time
    
    async with _vad_lock:
        # Record user start time
        _user_start_time = datetime.now().timestamp() * 1000
        
        # Wait for STT to provide transcript
        await asyncio.sleep(STT_CONFIRM_DELAY)
        
        # Build audio metadata
        audio_meta = {
            "vad": vad_confidence,
            "user_start": _user_start_time,
            "agent_start": _agent_start_time or 0,
            "rms": audio_rms,
        }
        
        if _last_stt_for_vad:
            # Analyze with full context
            decision = await manager.analyze(
                transcript=_last_stt_for_vad,
                agent_is_speaking=state.is_speaking(),
                audio_meta=audio_meta
            )
            _last_decision = decision
            
            log.info(
                f"VAD Stop Analysis | "
                f"Transcript: '{_last_stt_for_vad}' | "
                f"Decision: {decision} | "
                f"Engine: {manager.current_engine_name}"
            )
            
            # Decision logic
            if decision == "IGNORE" and state.is_speaking():
                # User said backchannel (yeah, ok) - keep speaking
                log.info("✓ VAD: IGNORE decision - Agent continues speaking")
                _last_stt_for_vad = None  # Clear for next event
                return
            
            elif decision == "INTERRUPT" and state.is_speaking():
                # User wants to interrupt (stop, wait, change, etc.)
                log.info("✗ VAD: INTERRUPT decision - Stopping agent")
                await stop_callback()
                
                # Process the user's intent after stopping
                if _intent_handler:
                    await _intent_handler(_last_stt_for_vad)
                
                _last_stt_for_vad = None
                return
        
        # Default: honor the stop (user finished speaking or no transcript)
        if state.is_speaking():
            log.debug("VAD: Default stop (no STT or NORMAL decision)")
            await stop_callback()
        
        _last_stt_for_vad = None

# =====================================================================
# 3. STT HOOK - Enhanced with parallel processing
# =====================================================================

async def on_stt_partial(transcript: str, is_final: bool = False):
    """
    Handles incoming STT transcripts with parallel interrupt detection.
    
    :param transcript: The transcribed text
    :param is_final: Whether this is a final transcript
    """
    global _last_stt_for_vad, _last_decision, _stt_timestamp, _user_start_time
    
    if not transcript or not transcript.strip():
        return
    
    # Update state for VAD handler
    _last_stt_for_vad = transcript
    _stt_timestamp = datetime.now().timestamp() * 1000
    
    if not _user_start_time:
        _user_start_time = _stt_timestamp
    
    # Build audio metadata
    audio_meta = {
        "vad": 1.0,
        "user_start": _user_start_time,
        "agent_start": _agent_start_time or 0,
        "rms": 0.01,  # Default mid-range value
    }
    
    log.debug(f"STT Partial: '{transcript}' | Final: {is_final} | Agent Speaking: {state.is_speaking()}")
    
    if state.is_speaking():
        # PARALLEL CHECK: Immediate interrupt detection while agent is speaking
        decision = await manager.analyze(
            transcript=transcript,
            agent_is_speaking=True,
            audio_meta=audio_meta
        )
        _last_decision = decision
        
        if decision == "INTERRUPT":
            # Hard interrupt detected - stop immediately
            log.warning(f"🛑 STT: HARD INTERRUPT detected: '{transcript}'")
            await _stop_tts_immediately()
            
            # Handle the user's request
            if _intent_handler and is_final:
                await _intent_handler(transcript)
            
            return
        
        elif decision == "IGNORE":
            # Backchannel - log but don't stop
            log.debug(f"✓ STT: Backchannel ignored: '{transcript}'")
            return
        
        # NORMAL: Let VAD handler decide based on timing
        log.debug(f"➜ STT: NORMAL utterance, VAD will decide: '{transcript}'")
    
    else:
        # Agent is silent - process user input normally
        decision = await manager.analyze(
            transcript=transcript,
            agent_is_speaking=False,
            audio_meta=audio_meta
        )
        
        if decision != "IGNORE" and is_final:
            log.info(f"📝 STT: Agent silent, processing: '{transcript}'")
            if _intent_handler:
                await _intent_handler(transcript)
        else:
            log.debug(f"⊘ STT: Input ignored (noise/filler): '{transcript}'")

# =====================================================================
# 4. HELPER FUNCTIONS
# =====================================================================

async def _stop_tts_immediately():
    """Stop the agent's TTS playback immediately."""
    if _tts_stream:
        try:
            await _tts_stream.aclose()  # LiveKit method to stop TTS stream
            log.info("✓ TTS stream stopped successfully")
        except Exception as e:
            log.error(f"✗ Error stopping TTS stream: {e}")
    else:
        log.warning("⚠ TTS stream not set - cannot stop playback")

async def _handle_user_intent(text: str):
    """
    Process user intent through the registered handler.
    This is the fallback if _intent_handler is not set.
    """
    if _intent_handler:
        await _intent_handler(text)
    else:
        log.warning(f"⚠ No intent handler registered for: '{text}'")

# =====================================================================
# 5. UTILITY FUNCTIONS
# =====================================================================

def get_last_decision() -> Optional[str]:
    """Get the last interruption decision made."""
    return _last_decision

def reset_state():
    """Reset all state variables (useful for testing)."""
    global _last_stt_for_vad, _last_decision, _stt_timestamp
    global _agent_start_time, _user_start_time
    
    _last_stt_for_vad = None
    _last_decision = None
    _stt_timestamp = None
    _agent_start_time = None
    _user_start_time = None
    
    log.info("State reset complete")

def get_manager_stats() -> dict:
    """Get current manager statistics."""
    return {
        "current_engine": manager.current_engine_name,
        "agent_speaking": state.is_speaking(),
        "last_decision": _last_decision,
        "last_transcript": _last_stt_for_vad,
    }