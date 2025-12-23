"""
Configuration for intelligent interruption handling.

This module defines configurable word lists for backchannel detection
and interruption filtering.
"""

import os
from typing import Set

# Optional: Load from .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, use system environment variables only
    pass

# Backchannel words - passive acknowledgments that should be ignored when agent is speaking
DEFAULT_BACKCHANNEL_WORDS: Set[str] = {
    "yeah"
    "yeah.",
    "ok.",
    "okay.",
    "hmm",
    "mhm",
    "uh-huh",
    "uh huh",
    "right",
    "aha",
    "huh"
    "ahaa"
    "ah",
    "yep",
    "yup",
    "sure",
    "gotcha",
    "got it",
    "i see",
    "alright",
}

# Interruption commands - words that should always interrupt
DEFAULT_INTERRUPTION_COMMANDS: Set[str] = {
    "wait",
    "stop",
    "no",
    "hold on",
    "hold up",
    "pause",
    "hang on",
    "but",
    "however",
    "actually",
}


def get_backchannel_words() -> Set[str]:
    """
    Get the list of backchannel words from environment or use default.
    
    Environment variable: LIVEKIT_BACKCHANNEL_WORDS
    Format: Comma-separated list, e.g., "yeah,ok,hmm"
    
    Returns:
        Set of lowercase backchannel words
    """
    env_words = os.getenv("LIVEKIT_BACKCHANNEL_WORDS")
    if env_words:
        # Split by comma and strip whitespace, convert to lowercase
        return {word.strip().lower() for word in env_words.split(",") if word.strip()}
    return DEFAULT_BACKCHANNEL_WORDS.copy()


def get_interruption_commands() -> Set[str]:
    """
    Get the list of interruption command words from environment or use default.
    
    Environment variable: LIVEKIT_INTERRUPTION_COMMANDS
    Format: Comma-separated list, e.g., "wait,stop,no"
    
    Returns:
        Set of lowercase interruption command words
    """
    env_words = os.getenv("LIVEKIT_INTERRUPTION_COMMANDS")
    if env_words:
        return {word.strip().lower() for word in env_words.split(",") if word.strip()}
    return DEFAULT_INTERRUPTION_COMMANDS.copy()


# Export for easy access
BACKCHANNEL_WORDS = get_backchannel_words()
INTERRUPTION_COMMANDS = get_interruption_commands()
