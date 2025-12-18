# event_hooks.py
import asyncio
import logging
from .interruption_manager import InterruptionManager
from .state_observer import AgentStateObserver
from .config import STT_CONFIRM_DELAY, STT_MAX_WAIT

log = logging.getLogger("interrupt_hooks")

# --- SINGLETONS ---
state = AgentStateObserver()

# CHANGE: No arguments needed. Manager loads Mode & Lists from config.py/Env
manager = InterruptionManager() 

# --- STATE VARIABLES ---
_last_stt_for_vad = None
_last_decision = None
_vad_lock = asyncio.Lock()

async def on_tts_start():
    state.on_speaking_start()

async def on_tts_end():
    state.on_speaking_end()

async def vad_stop_event_handler(vad_event_id: str, stop_callback):
    """
    Delays VAD stop to check for 'IGNORE' or 'INTERRUPT' intent.
    """
    global _last_stt_for_vad, _last_decision
    
    async with _vad_lock:
        # Wait for STT to catch up (latency buffer)
        await asyncio.sleep(STT_CONFIRM_DELAY)
        
        if _last_stt_for_vad:
            # CHANGE: analyze() signature is same, but internal logic is now Switchable/Hybrid
            decision = await manager.analyze(_last_stt_for_vad, state.is_speaking())
            
            _last_decision = decision
            log.debug(f"VAD: STT arrived '{_last_stt_for_vad}' -> {decision}")
            
            if decision == "IGNORE" and state.is_speaking():
                log.debug("VAD: canceling stop (Passive acknowledgment)")
                return # Don't call stop_callback

            if decision == "INTERRUPT" and state.is_speaking():
                log.debug("VAD: honoring interrupt")
                await stop_callback()
                return

        # Default fallback: if no STT or NORMAL, honor VAD stop
        log.debug("VAD: Default stop")
        await stop_callback()

async def on_stt_partial(transcript: str):
    """
    Feeds STT into the manager. If 'INTERRUPT' is detected mid-stream, 
    we kill audio immediately without waiting for VAD.
    """
    global _last_stt_for_vad, _last_decision
    _last_stt_for_vad = transcript
    
    if state.is_speaking():
        # Async analysis (supports LLM latency)
        decision = await manager.analyze(transcript, True)
        _last_decision = decision
        
        if decision == "INTERRUPT":
            log.info(f"Hard Interrupt detected: '{transcript}'")
            await _stop_tts_immediately()
            await _handle_user_intent(transcript)
    else:
        # Agent silent -> process normally
        if decision != "IGNORE":
            log.info(f"Non ignorable text detected: '{transcript}'")        
            await _handle_user_intent(transcript)

# --- Placeholders ---
async def _stop_tts_immediately():
    # Call your Agent's actual stop method here
    pass

async def _handle_user_intent(text):
    # Pass to your LLM / Agent logic
    pass