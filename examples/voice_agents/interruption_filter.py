"""
Smart Interruption Filter for Voice Agents

This module provides intelligent filtering to distinguish between:
- PASSIVE words (backchanneling): User acknowledgments that shouldn't interrupt the agent
- ACTIVE words (commands): User commands that should immediately stop the agent
"""

import re

#PASSIVE WORDS (Backchanneling)
# The agent will completely IGNORE these words while speaking.
PASSIVE_WORDS = {
    "yeah", "yep", "yes", "yup", "ok", "okay", "alright", "right",
    "uh-huh", "uh huh", "hmm", "mhm", "aha", "sure", "got it", "i see",
    "understood", "cool", "great", "nice", "really", "absolutely",
    "exactly", "go on", "makes sense", "mhmm", "mm-hmm", "mmhmm",
    "oh", "mm", "mmm", "wow"
}

# ACTIVE WORDS (Commands)
# These trigger an IMMEDIATE stop, even if mixed with other words.
ACTIVE_WORDS = {
    "stop", "wait", "hold", "pause", "no", "nope", "cancel",
    "listen", "hang on", "excuse me", "actually", "wrong",
    "quiet", "shut up", "enough", "never mind", "nevermind"
}


def clean_text(text: str) -> str:
    """Removes punctuation and extra spaces for cleaner matching."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    return text


def should_interrupt_optimistic(text: str) -> bool:
    """
    FAST CHECK: Used for 'Interim Results' (partial text).
    Returns True ONLY if we see a clear command keyword immediately.
    
    This is the "fast path" - we want to react quickly to commands
    like "stop" or "wait" even before the full sentence is transcribed.
    """
    if not text:
        return False
        
    cleaned = clean_text(text)
    
    # Check if any active word is present in the partial text
    words = set(cleaned.split())
    
    # We check if any ACTIVE word is inside the user's input
    if not words.isdisjoint(ACTIVE_WORDS):
        return True
    
    return False


def should_interrupt_agent(text: str, is_speaking: bool) -> bool:
    """
    ROBUST CHECK: Used for 'Final Transcript'.
    Decides final action based on complete sentence.
    
    Args:
        text: The transcribed text from the user
        is_speaking: Whether the agent is currently speaking
        
    Returns:
        True if the agent should be interrupted, False if the input should be ignored
    """
    # If agent isn't speaking, always process input (it's a reply)
    if not is_speaking:
        return True

    if not text:
        return False

    cleaned = clean_text(text)
    words = set(cleaned.split())

    if not words:
        return False

    # ACTIVE COMMANDS take priority (Scenario: "Yeah but wait")
    # If the sentence contains ANY command word -> Interrupt
    if not words.isdisjoint(ACTIVE_WORDS):
        return True

    # PASSIVE ACKNOWLEDGEMENT (Scenario: "Yeah...")
    # If the input is ONLY passive words -> Ignore
    if cleaned in PASSIVE_WORDS:
        return False
    
    # Check if all words in the phrase are passive (e.g. "Oh yeah okay")
    if words.issubset(PASSIVE_WORDS):
        return False

    # DEFAULT SAFETY
    # If it's something complex we don't recognize, assume it's a real question -> Interrupt
    return True
