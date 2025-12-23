import logging
import os
import re

logger = logging.getLogger("backchannel-handler")

# ===========
# CONFIGURABLE BACKCHANNEL / COMMAND LISTS
# ===========

_DEFAULT_BACKCHANNEL_WORDS = {
    # Short Fillers & Continuers
    "ah", "aha", "hm", "hmm", "mhm", "mhmm",
    "mm-hmm", "mmhmm", "uh-huh", "um", "uh", "uhhuh",

    # Affirmations & Agreement
    "absolutely", "exactly", "indeed", "right", "sure",
    "true", "understood", "correct", "definitely",

    # Casual Acknowledgments
    "alright", "cool", "fine", "nice", "ok", "okay",
    "yeah", "yep", "yes", "yup", "sounds good",

    # Phrases & Feedback
    "go on", "got it", "i see", "makes sense",
    "keep going", "tell me more",

    # Reactions
    "really", "wow", "for real", "seriously",
    "interesting", "no way",
}

_DEFAULT_INTERRUPT_WORDS = {
    "stop",
    "wait",
    "no",
    "hold",
    "cancel",
    "pause",
    "enough",
    "hold on",
}


def _parse_word_list(env_name: str, default: set[str]) -> set[str]:
    """Parse word list from environment variable or use default."""
    raw = os.getenv(env_name)
    if not raw:
        return default
    return {w.strip().lower() for w in raw.split(",") if w.strip()}


def _normalize_tokens(text: str) -> list[str]:
    """Split on non-word characters, lowercased."""
    return [t for t in re.split(r"\W+", text.lower()) if t]


class BackchannelInterruptHandler:
    """
    Handles intelligent interruption logic for voice agents.
    Distinguishes between soft backchannels (acknowledgments) and real interrupts.
    """
    
    def __init__(self):
        self.backchannel_words = _parse_word_list("BACKCHANNEL_WORDS", _DEFAULT_BACKCHANNEL_WORDS)
        self.interrupt_words = _parse_word_list("INTERRUPT_WORDS", _DEFAULT_INTERRUPT_WORDS)
        self.agent_is_speaking = {"value": False}
        logger.info(f"Initialized with {len(self.backchannel_words)} backchannel words and {len(self.interrupt_words)} interrupt words")
    
    def is_soft_backchannel(self, text: str) -> bool:
        """
        Returns True if the utterance is ONLY made of backchannel words
        like 'yeah', 'ok', 'hmm', etc.
        """
        tokens = _normalize_tokens(text)
        if not tokens:
            return False
        return all(tok in self.backchannel_words for tok in tokens)
    
    def contains_strong_interrupt(self, text: str) -> bool:
        """
        Returns True if the utterance contains any strong interrupt word
        like 'stop', 'wait', 'no', 'cancel', etc.
        """
        tokens = _normalize_tokens(text)
        return any(tok in self.interrupt_words for tok in tokens)
    
    def update_agent_speaking_state(self, is_speaking: bool):
        """Update the internal state tracking whether agent is speaking."""
        self.agent_is_speaking["value"] = is_speaking
    
    def should_interrupt(self, text: str, is_final: bool) -> tuple[bool, str]:
        """
        Core decision logic for interruption handling.
        
        Returns:
            tuple[bool, str]: (should_interrupt, reason)
        """
        if not text.strip():
            return (False, "empty_text")
        
        # If agent is NOT speaking, allow normal behavior
        if not self.agent_is_speaking["value"]:
            logger.debug("User speaking while agent not speaking: %r (final=%s)", text, is_final)
            return (False, "agent_not_speaking")
        
        # Only process final transcripts to avoid jitter
        if not is_final:
            logger.debug("Interim transcript while speaking (ignored): %r", text)
            return (False, "interim_transcript")
        
        logger.info("User spoke while agent is speaking: %r", text)
        
        # Check for soft backchannel
        if self.is_soft_backchannel(text):
            logger.info("Ignoring soft backchannel while agent is speaking: %r", text)
            return (False, "soft_backchannel")
        
        # Check for strong interrupt words
        if self.contains_strong_interrupt(text):
            logger.info("Detected strong interrupt while agent speaking: %r", text)
            return (True, "strong_interrupt")
        
        # Mixed or non-backchannel content while agent is speaking
        logger.info("Detected mixed/non-soft input while speaking: %r", text)
        return (True, "mixed_input")