# livekit/agents/voice/interrupt_handler.py
"""
InterruptHandler - rule-based, production-quality interrupt handler.

This module provides a rule-based interrupt handler that prevents agents from being
cut off by backchannel words ("yeah", "ok", "hmm") while still allowing real interrupts
("stop", "wait", "no"). The handler uses a short confirmation window (default 120-180ms)
to collect STT partials and make interrupt decisions.
"""
import threading
import time
import logging
from typing import Optional, Callable

LOG = logging.getLogger("interrupt_handler")
LOG.setLevel(logging.INFO)

_DEFAULT_CONFIG = {
    "soft_words": [
        "yeah", "ok", "okay", "hmm", "uh-huh", "mhm", "mm-hmm", "right", "yah", "yep", "yup"
    ],
    "hard_words": [
        "stop", "wait", "no", "pause", "hold on", "hold up", "cut", "cancel"
    ],
    "stt_confirm_ms": 150,  # Default confirmation window (120-180ms range)
    "stt_confirm_max_ms": 300,
    "extend_ms_on_unclear": 80,
    "debug": False
}

def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return text.lower().strip()

class InterruptHandler:
    """
    Rule-based interrupt handler for voice agents.
    
    This handler distinguishes between backchannel words (soft words) and real
    interrupts (hard words) by using a short confirmation window when VAD detects
    speech while the agent is speaking.
    
    Args:
        audio_player: Audio player object with methods:
            - is_playing() -> bool: Returns True if audio is currently playing
            - pause(): Pauses audio playback
            - resume(): Resumes audio playback
            - stop(): Stops audio playback
        config: Optional configuration dict with keys:
            - soft_words: List of backchannel words to ignore (default: ["yeah", "ok", ...])
            - hard_words: List of interrupt words that trigger immediate stop (default: ["stop", "wait", ...])
            - stt_confirm_ms: Confirmation window duration in milliseconds (default: 150)
            - stt_confirm_max_ms: Maximum confirmation window duration (default: 300)
            - debug: Enable debug logging (default: False)
    
    Callbacks:
        on_interrupt: Called when an interrupt is detected. Receives transcript text.
        on_immediate_user_speech: Called when user speaks while agent is silent.
    """
    
    def __init__(self, audio_player, config: Optional[dict] = None):
        """
        Initialize the interrupt handler.
        
        Args:
            audio_player: Audio player with is_playing(), pause(), resume(), stop() methods
            config: Optional configuration dictionary
        """
        cfg = dict(_DEFAULT_CONFIG)
        if config:
            cfg.update(config)
        self.cfg = cfg
        self.audio_player = audio_player

        self.on_interrupt: Optional[Callable[[str], None]] = None
        self.on_immediate_user_speech: Optional[Callable[[], None]] = None

        self._pending_timer: Optional[threading.Timer] = None
        self._pending_started_at = 0.0
        self._collected_transcript = ""
        self._collected_confidence = 0.0

        if self.cfg.get("debug"):
            LOG.setLevel(logging.DEBUG)

    def on_vad(self):
        """
        Called when VAD detects start-of-speech.
        
        If agent is silent, immediately routes to on_immediate_user_speech.
        If agent is speaking, starts a confirmation window to collect STT partials.
        """
        # If a confirmation window is already active, ignore duplicate VADs.
        # This prevents the handler from treating the pause (from starting the
        # confirmation window) as a new user turn.
        if self._pending_timer is not None:
            LOG.debug("Confirmation window already active, ignoring VAD")
            return

        if not self.audio_player.is_playing():
            if self.on_immediate_user_speech:
                LOG.debug("Agent silent, routing immediate user speech")
                self.on_immediate_user_speech()
            return

        LOG.debug("Agent speaking, starting confirmation window")
        self._start_confirmation_window()


    def on_stt_partial(self, text: str, confidence: float = 0.0):
        """
        Called with streaming partial transcripts.
        
        Args:
            text: Partial transcript text
            confidence: Confidence score (0.0-1.0)
        
        If a hard word is detected in partials, interrupts immediately.
        """
        if self._pending_timer is None:
            return
        self._collected_transcript = (text or "").strip()
        self._collected_confidence = confidence
        if self._contains_hard_word(self._collected_transcript):
            LOG.debug(f"Hard word detected in partial: {self._collected_transcript}")
            self._cancel_pending()
            self._do_interrupt(self._collected_transcript)

    def on_stt_final(self, text: str, confidence: float = 1.0):
        """
        Called with final transcript.
        
        Args:
            text: Final transcript text
            confidence: Confidence score (0.0-1.0)
        
        Cancels the confirmation window and makes interrupt decision.
        """
        if self._pending_timer is None:
            return
        self._collected_transcript = (text or "").strip()
        self._collected_confidence = confidence
        self._cancel_pending()
        self._decide_from_transcript(self._collected_transcript)

    def _start_confirmation_window(self):
        """Start a short confirmation window, pausing TTS and collecting STT partials."""
        try:
            self.audio_player.pause()
            LOG.debug("Audio paused for confirmation window")
        except Exception as e:
            LOG.warning(f"Failed to pause audio: {e}")
        self._collected_transcript = ""
        self._collected_confidence = 0.0
        self._pending_started_at = time.time()
        base_ms = self.cfg["stt_confirm_ms"]
        self._pending_timer = threading.Timer(base_ms / 1000.0, self._on_timeout)
        self._pending_timer.start()
        LOG.debug(f"Confirmation window started: {base_ms}ms")

    def _on_timeout(self):
        self._pending_timer = None
        self._decide_from_transcript(self._collected_transcript)

    def _cancel_pending(self):
        if self._pending_timer:
            try:
                self._pending_timer.cancel()
            except:
                pass
        self._pending_timer = None

    def _decide_from_transcript(self, transcript: str):
        t = _normalize_text(transcript)
        if not t:
            self._resume()
            return
        if self._contains_hard_word(t):
            self._do_interrupt(transcript)
            return
        if self._is_soft_only(t):
            self._resume()
            return
        self._do_interrupt(transcript)

    def _do_interrupt(self, transcript: str):
        """Execute interrupt: stop audio and call on_interrupt callback."""
        try:
            self.audio_player.stop()
            LOG.debug(f"Audio stopped due to interrupt: {transcript}")
        except Exception as e:
            LOG.warning(f"Failed to stop audio: {e}")
        if self.on_interrupt:
            self.on_interrupt(transcript)

    def _resume(self):
        """Resume audio playback (soft words detected, no interrupt)."""
        try:
            self.audio_player.resume()
            LOG.debug("Audio resumed (soft words only, no interrupt)")
        except Exception as e:
            LOG.warning(f"Failed to resume audio: {e}")

    def _contains_hard_word(self, text: str) -> bool:
        t = _normalize_text(text)
        for w in self.cfg["hard_words"]:
            if w in t:
                return True
        return False

    def _is_soft_only(self, text: str) -> bool:
        t = _normalize_text(text)
        tokens = t.split()
        if not tokens:
            return False
        for tok in tokens:
            if tok not in self.cfg["soft_words"]:
                return False
        return True

