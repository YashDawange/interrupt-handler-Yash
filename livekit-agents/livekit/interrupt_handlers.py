# livekit-agents/livekit/interrupt_handlers.py
import logging
import threading

from .interrupt_config import load_lists
from .agent_state import GLOBAL_STATE
from .interrupt_filter import InterruptFilter, Decision

logger = logging.getLogger("livekit.interrupt")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
logger.addHandler(ch)

IGNORE_WORDS, INTERRUPT_WORDS = load_lists(config_path=None)
FILTER = InterruptFilter(IGNORE_WORDS, INTERRUPT_WORDS)

# AGENT_CONTROL must be replaced/wired with your agent TTS/STT control object
class AgentControlPlaceholder:
    def stop_speaking(self):
        logger.info("[AGENT] stop_speaking() called")

    def continue_speaking(self):
        logger.info("[AGENT] continue_speaking() called")

    def respond_to_user(self, transcript):
        logger.info(f"[AGENT] respond_to_user(): '{transcript}'")

AGENT_CONTROL = AgentControlPlaceholder()

def on_vad_detected():
    """
    Called by VAD event (fast). Do NOT stop playback here.
    Instead, set pending flag and wait for STT.
    """
    logger.info("[VAD] detected user audio -> setting pending_vad")
    GLOBAL_STATE.set_pending_vad(True)
    # small watchdog so agent doesn't wait forever for STT (adjust ms as needed)
    threading.Timer(0.6, _vad_watchdog_timeout).start()

def _vad_watchdog_timeout():
    if GLOBAL_STATE.get_pending_vad():
        logger.warning("[VAD WATCHDOG] STT not arrived within timeout.")
        if GLOBAL_STATE.is_speaking():
            logger.info("[VAD WATCHDOG] Agent is speaking -> force INTERRUPT to be safe.")
            GLOBAL_STATE.set_pending_vad(False)
            AGENT_CONTROL.stop_speaking()
        else:
            GLOBAL_STATE.set_pending_vad(False)

def on_stt_result(transcript: str):
    pending = GLOBAL_STATE.get_pending_vad()
    logger.info(f"[STT] transcript received: '{transcript}' pending_vad={pending}")

    if pending:
        GLOBAL_STATE.set_pending_vad(False)
        decision = FILTER.decide(transcript, GLOBAL_STATE.is_speaking())
        logger.info(f"[INTERRUPT] speaking={GLOBAL_STATE.is_speaking()} transcript='{transcript}' decision={decision}")
        _apply_decision(decision, transcript)
    else:
        # no pending vad: treat normally
        decision = FILTER.decide(transcript, GLOBAL_STATE.is_speaking())
        _apply_decision(decision, transcript)

def _apply_decision(decision, transcript):
    if decision == Decision.IGNORE:
        logger.info("[INTERRUPT] IGNORE -> continue speaking")
        AGENT_CONTROL.continue_speaking()
    elif decision == Decision.INTERRUPT:
        logger.info("[INTERRUPT] INTERRUPT -> stop speaking immediately")
        AGENT_CONTROL.stop_speaking()
    elif decision == Decision.RESPOND:
        logger.info("[INTERRUPT] RESPOND -> agent will process input")
        AGENT_CONTROL.respond_to_user(transcript)
    else:
        logger.info("[INTERRUPT] UNKNOWN -> fallback behavior")
        if GLOBAL_STATE.is_speaking():
            AGENT_CONTROL.continue_speaking()
        else:
            AGENT_CONTROL.respond_to_user(transcript)

# helpers for TTS lifecycle wiring
def on_tts_start():
    logger.info("[TTS] start")
    GLOBAL_STATE.set_speaking(True)

def on_tts_end():
    logger.info("[TTS] end")
    GLOBAL_STATE.set_speaking(False)
