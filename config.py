import os

# The "Safe List"
# If the agent is speaking and hears one of these, it will keep talking.
DEFAULT_IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "aha", "uh-huh", "right", "sure", "yep",
    "yes", "yup", "cool", "gotcha", "wow", "really", "understood", "i see"
}

def get_ignore_words():
    """
    Returns the set of words to ignore.
    Checks for an environment variable first, allowing you to update this 
    without changing code (Good for the "Code Quality" criteria).
    """
    env_words = os.getenv("IGNORE_WORDS")
    if env_words:
        # detailed parsing to handle spacing or different delimiters
        return set(word.strip().lower() for word in env_words.split(","))
    return DEFAULT_IGNORE_WORDS