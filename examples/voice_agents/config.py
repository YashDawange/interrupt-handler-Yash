import os

# 1. Define the default list of "soft" inputs 
DEFAULT_IGNORE_WORDS = ['yeah', 'ok', 'hmm', 'right', 'uh-huh']

# 2. Function to fetch words (satisfies "Configurable" requirement )
def get_ignore_words():
    # Check if an environment variable 'IGNORE_WORDS' is set
    env_words = os.getenv("IGNORE_WORDS")
    if env_words:
        # Split by comma and strip whitespace
        return [word.strip().lower() for word in env_words.split(",")]
    return DEFAULT_IGNORE_WORDS