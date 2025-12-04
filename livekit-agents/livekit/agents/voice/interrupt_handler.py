from typing import Literal
import re

# Complete list of filler words to ignore when agent is speaking
IGNORE_WORDS = {
    # Yeah variations
    "yeah", "ya", "yep", "yup", "yes", "yea", "yah", "yuh",
    
    # Okay variations  
    "ok", "okay", "okey", "okie", "k", "kk", "kay", "oke", "okey-dokey",
    "okey dokey", "okie dokie", "okeydokey", 
    
    # Right variations
    "right", "rite", "ryt", "alright", "all right", "righto",
    "right on", "right then", "right you are",
    
    # Hmm variations
    "hmm", "hm", "hmmm", "hmph",
    
    # Other common fillers
    "uh", "um", "mm", "mhm", "aha", "uh huh", "uh-huh",
    "sure", "got it", "i see", "cool", "fine", "good", 
    "great", "nice", "roger", "very good", "well", "exactly",
    "indeed", "absolutely", "certainly", "definitely", "of course",
    "surely", "true", "correct", "affirmative", "agreed",
    
    # Aha variations
    "aha", "ah", "ahh", "aah",
}

# Complete list of interrupt commands
INTERRUPT_COMMANDS = {
    "stop", "wait", "no", "hold", "hold on", "stop it",
    "pause", "break", "shut up", "quiet", "enough", "halt",
    "cancel", "abort", "quit", "end", "cease", "desist",
    "finish", "terminate", "discontinue", "cut", "cut it out",
    "knock it off", "give it a rest", "stfu",
}

Decision = Literal["normal", "ignore", "interrupt"]

def _normalize_word(word: str) -> str:
    """Normalize a word for comparison."""
    word = word.lower().strip()
    
    # Remove trailing punctuation
    word = word.rstrip('.,!?;:')
    
    # Convert common variations
    if word == "k":
        return "ok"
    if word == "yep" or word == "yup":
        return "yeah"
    if word == "rite" or word == "ryt":
        return "right"
    if word == "hm":
        return "hmm"
    
    return word

def _is_filler_word(word: str) -> bool:
    """Check if a word is a filler word."""
    normalized = _normalize_word(word)
    
    # Direct match
    if normalized in IGNORE_WORDS:
        return True
    
    # Pattern matches for common variations
    patterns = [
        r'^o?k(ay)?(ey)?(ie)?(dokey)?$',  # okay variations
        r'^r(ight|ite|yt)(o)?$',         # right variations  
        r'^y(eah|ep|up|a|ah)?$',         # yeah variations
        r'^uh?h?$',                      # uh, uhh
        r'^um?m?$',                      # um, umm
        r'^hm{1,3}$',                    # hmm, hmmm
        r'^mhm$',                        # mhm
        r'^ah{1,3}$',                    # aha, ahh
    ]
    
    for pattern in patterns:
        if re.match(pattern, normalized):
            return True
    
    return False

def _is_interrupt_command(text: str) -> bool:
    """Check if text contains an interrupt command."""
    text_lower = text.lower()
    
    # Check each interrupt command
    for command in INTERRUPT_COMMANDS:
        # Use word boundary matching to avoid partial matches
        pattern = r'\b' + re.escape(command) + r'\b'
        if re.search(pattern, text_lower):
            return True
    
    return False

def _contains_only_fillers(words) -> bool:
    """Check if all words in list are filler words."""
    for word in words:
        if not _is_filler_word(word):
            return False
    return True

def classify_transcript(text: str, agent_speaking: bool) -> Decision:
    """
    Classify user speech for intelligent interruption handling.
    
    Returns:
        "ignore": Filler words while agent is speaking (should be ignored)
        "interrupt": Contains interrupt command (should interrupt)
        "normal": Normal speech to respond to
    """
    if not text or not text.strip():
        return "normal"
    
    # Clean the text
    text_clean = text.lower().strip()
    
    # Remove punctuation but keep spaces
    text_clean = re.sub(r'[^\w\s]', ' ', text_clean)
    
    # Collapse multiple spaces
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()
    
    # Split into words
    words = text_clean.split()
    
    # **RULE 1: Agent NOT speaking - everything is normal input**
    if not agent_speaking:
        return "normal"
    
    # **RULE 2: Check for interrupt commands FIRST (highest priority)**
    # If any interrupt command is present, interrupt immediately
    if _is_interrupt_command(text_clean):
        return "interrupt"
    
    # **RULE 3: Check if ALL words are filler words**
    if words and _contains_only_fillers(words):
        return "ignore"
    
    # **RULE 4: Default - normal speech that should interrupt**
    return "normal"