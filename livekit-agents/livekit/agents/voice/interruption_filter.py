"""
Intelligent Interruption Filter for LiveKit Agents

Distinguishes between passive acknowledgements (backchannels) and active interruptions.
"""

import re
from typing import Set

PASSIVE_WORDS: Set[str] = {
    "yeah", "yep", "yes", "yup", "ya", "yea",
    "ok", "okay", "k", "okey", "kay",
    "uh-huh", "uh huh", "uhuh", "uhhuh",
    "mhm", "mm-hmm", "mmhmm", "mm", "hmm", "hm", "mmm",
    "right", "sure", "alright", "all right", "aight",
    "got it", "gotcha", "i see", "i understand", "understood",
    "ah", "oh", "aha", "ooh", "wow",
    "cool", "nice", "great", "good", "fine", "awesome",
}

ACTIVE_WORDS: Set[str] = {
    "wait", "stop", "hold", "pause", "hang",
    "hold on", "hold up", "hang on", "wait wait",
    "but", "however", "actually", "no", "nope", "nah",
    "excuse me", "sorry", "hey",
    "question", "can i", "let me", "may i",
    "what", "why", "how", "when", "where",
    "wrong", "incorrect", "that's not", "thats not",
}


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = ' '.join(text.split())
    return text


def is_passive_acknowledgement(transcript: str) -> bool:
    """Check if transcript is a passive acknowledgement (backchannel)."""
    if not transcript:
        return False
    
    normalized = normalize_text(transcript)
    if not normalized:
        return False
    
    if normalized in PASSIVE_WORDS:
        return True
    
    words = normalized.split()
    if len(words) <= 3 and words[0] in PASSIVE_WORDS:
        return True
    
    return False


def is_active_interruption(transcript: str) -> bool:
    """Check if transcript is an active interruption."""
    if not transcript:
        return False
    
    normalized = normalize_text(transcript)
    if not normalized:
        return False
    
    for phrase in ACTIVE_WORDS:
        if normalized.startswith(phrase):
            return True
    
    return False


def should_interrupt_agent(transcript: str, agent_is_speaking: bool) -> bool:
    """Main decision function: Should we interrupt the agent?"""
    if not agent_is_speaking:
        return True
    
    if is_passive_acknowledgement(transcript):
        return False
    
    if is_active_interruption(transcript):
        return True
    
    return True


def is_transcript_passive_only(transcript: str) -> bool:
    """Check if transcript consists ONLY of passive acknowledgements."""
    if not transcript:
        return False
    
    if is_active_interruption(transcript):
        return False
    
    normalized = normalize_text(transcript)
    words = normalized.split()
    
    if not words:
        return False
    
    for word in words:
        if word not in PASSIVE_WORDS:
            return False
    
    return True


def is_interruption_command_only(transcript: str) -> bool:
    """Check if transcript consists ONLY of interruption commands."""
    if not transcript:
        return False
    
    normalized = normalize_text(transcript)
    if not normalized:
        return False
    
    if normalized in ACTIVE_WORDS:
        return True
    
    words = normalized.split()
    if not words:
        return False
    
    pure_stop_commands = {
        "wait", "stop", "hold", "pause", "hang",
        "no", "nope", "nah",
    }
    
    if len(set(words)) == 1 and words[0] in pure_stop_commands:
        return True
    
    if all(word in pure_stop_commands for word in words):
        return True
    
    return False

