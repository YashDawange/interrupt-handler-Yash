# logic.py

# ---------------------------------------------------------------------
# 1. IGNORE LIST (Backchanneling / Fillers)
# ---------------------------------------------------------------------
# These are words the agent should IGNORE if spoken while it is already talking.
IGNORE_WORDS = {
    # -- Affirmations & Agreements --
    "yeah", "yea", "yah", "yes", "yep", "yup", "yus",
    "ok", "okay", "k", "kk", "okie",
    "right", "correct", "sure", "surely", "absolutely", "exactly",
    "alright", "fine", "indeed", "certainly",
    
    # -- Sounds / Non-lexical fillers --
    "hmm", "hm", "mhm", "mhmm", "mmhmm", "mm-hmm", "mm", "mmm",
    "uh-huh", "uhhuh", "uh", "um", "huh", "ah", "aha", "oh",
    "ohh", "ooh", "whoa", "wow",
    
    # -- Encouragement / Understanding --
    "cool", "nice", "great", "awesome", "perfect",
    "gotcha", "got", "it", "see", "understood",
    "interesting", "makes", "sense", "go", "on", "continue"
}

# Phrases that are safe to ignore (multi-word checks)
# If the user says EXACTLY these phrases, we ignore.
IGNORE_PHRASES = {
    "got it", "i see", "makes sense", "go on", "keep going", 
    "that's right", "thats right", "sounds good", "fair enough",
    "mm hmm", "uh huh", "oh okay", "ah i see"
}

# ---------------------------------------------------------------------
# 2. URGENT LIST (Interruptions)
# ---------------------------------------------------------------------
# If ANY of these words appear, the agent must STOP immediately.
URGENT_COMMANDS = {
    # -- Stop / Pause --
    "stop", "wait", "hold", "pause", "halt", "cease", "cancel",
    "silence", "quiet", "shut", "enough",
    
    # -- Correction / Negation --
    "no", "nope", "nah", "wrong", "incorrect", "false",
    "actually", "mistake", "error",
    
    # -- Attention Grabbing --
    "hey", "hello", "listen", "look", "yo", "excuse", "pardon",
    "question", "query", "ask", "repeat", "say", "again", "what"
}

def should_interrupt(text: str) -> bool:
    """
    Decides if the agent should stop talking.
    
    Logic Flow:
    1. Clean the text (remove punctuation, handle hyphens).
    2. Check for URGENT commands (Stop immediately).
    3. Check for IGNORE phrases (exact match).
    4. Check word-by-word:
       - If ALL words are in IGNORE_WORDS -> Ignore (False).
       - If ANY word is unknown/meaningful -> Interrupt (True).
       
    Returns:
        True  -> Interrupt (Agent stops).
        False -> Ignore (Agent keeps talking).
    """
    
    # 1. Normalization
    # Lowercase and strip whitespace
    raw_text = text.lower().strip()
    
    # Create a "clean" version without punctuation for word matching
    # We remove dashes so "mm-hmm" becomes "mmhmm" (easier to match)
    cleaned_text = raw_text
    for char in [".", ",", "!", "?", ";", ":", "-", "_"]:
        cleaned_text = cleaned_text.replace(char, "")
        
    words = cleaned_text.split()
    
    if not words:
        return False

    # -------------------------------------------------------
    # RULE 1: Urgent Commands (Highest Priority)
    # -------------------------------------------------------
    # Example: "Yeah wait a sec" -> Contains "wait" -> Interrupt.
    if any(word in URGENT_COMMANDS for word in words):
        return True
        
    # Check for "hang on", "one sec" (multi-word urgencies)
    if "hang on" in raw_text or "one sec" in raw_text or "just a sec" in raw_text:
        return True

    # -------------------------------------------------------
    # RULE 2: Exact Phrase Matching
    # -------------------------------------------------------
    # Check if the raw input (minus punctuation) matches a safe phrase
    # Example: "makes sense" is in IGNORE_PHRASES
    if cleaned_text in [p.replace(" ", "") for p in IGNORE_PHRASES]:
        return False
    
    # Also check the raw text against phrases
    if raw_text in IGNORE_PHRASES:
        return False

    # -------------------------------------------------------
    # RULE 3: Word-by-Word Analysis
    # -------------------------------------------------------
    # If every single word in the sentence is a known filler, we ignore.
    # If there is even ONE "real" word (e.g. "Apple"), we interrupt.
    
    for word in words:
        # Check 1: Is the word directly in the ignore list?
        if word in IGNORE_WORDS:
            continue
            
        # Check 2: Handle "mmhmm" variations created by cleaning
        # If user said "mm-hmm", cleaning made it "mmhmm". 
        # We need to ensure "mmhmm" is allowed.
        if word in ["mmhmm", "uhhuh", "okey", "okayy"]:
            continue
            
        # If we get here, we found a word that is NOT a filler.
        # Example: User said "Yeah but..." -> "but" is not in ignore list.
        # Result: INTERRUPT.
        return True

    # If we finished the loop, all words were fillers.
    # Result: IGNORE.
    return False