import re

# Words that should NOT stop the agent from talking
BACKCHANNEL_WORDS = {
    "yeah", "yep", "yes", "ok", "okay", "alright", "uh-huh", "hmm", 
    "mhm", "sure", "got it", "i see", "cool", "great", "really", "wow"
}

# Words that MUST stop the agent immediately
COMMAND_WORDS = {
    "stop", "wait", "hold", "pause", "no", "cancel", "actually", 
    "wrong", "quiet", "shut up", "enough", "nevermind"
}

def normalize_text(text: str) -> str:
    """Cleans punctuation and casing for accurate comparison."""
    if not text:
        return ""
    return re.sub(r'[^\w\s]', '', text.lower().strip())

def is_priority_command(text: str) -> bool:
    """Checks if the user said a specific 'Stop' command."""
    cleaned = normalize_text(text)
    words = set(cleaned.split())
    return not words.isdisjoint(COMMAND_WORDS)

def validate_interruption(text: str, agent_is_speaking: bool) -> bool:
    """
    Determines if a transcript is significant enough to stop the agent.
    Returns True to interrupt, False to ignore.
    """
    if not agent_is_speaking:
        return True # Always listen if agent is silent

    cleaned = normalize_text(text)
    words = set(cleaned.split())

    if not words:
        return False

    # 1. Check for hard stop commands
    if not words.isdisjoint(COMMAND_WORDS):
        return True

    # 2. If it's just backchanneling, don't interrupt
    if words.issubset(BACKCHANNEL_WORDS):
        return False

    # 3. If the user said something substantial, interrupt
    return True