"""
Configurable word lists for intelligent interrupt filtering.
"""

from __future__ import annotations

import os
from typing import Iterable

# ============================================================================
# DEFAULT IGNORE WORDS (Passive acknowledgements / Backchanneling)
# ============================================================================

DEFAULT_IGNORE_WORDS: frozenset[str] = frozenset([
    # Affirmative / short acknowledgements
    "yes", "yeah", "yep", "yup", "ya",
    "ok", "okay", "k", "kk",
    "right", "alright", "sure",
    "cool", "nice", "great",
    "aha", "ah", "oh",
    "i see", "got it", "gotcha",

    # Humming / thinking sounds (very common in speech)
    "hmm", "hm", "hmmm", "hmmmm",
    "mm", "mmm", "mmmm",
    "mhm", "mhmm", "mmhmm",
    "mm-hmm", "mm hmm",
    "hmm-hmm", "hm-hm",

    # Agreement sounds
    "uh-huh", "uh huh", "uhuh", "uhhuh",
    "uh-hm", "uh hm",

    # Hesitation / filler sounds
    "um", "umm", "ummm",
    "uh", "uhh", "uhhh",
    "er", "err", "errr",
    "ahh", "ahhh",
    "ohh", "ohhh",

    # Casual conversational fillers
    "you know",
    "i see",
    "sort of",
    "kind of",

    # Common STT artifacts / trailing fillers
    "huh",
    "eh",
])


# ============================================================================
# DEFAULT INTERRUPT WORDS (Active command words)
# ============================================================================

DEFAULT_INTERRUPT_WORDS: frozenset[str] = frozenset([
    # Stop commands
    "stop", "wait", "hold", "pause",
    
    # Negation / Cancel
    "no", "nope", "cancel", "quit",
    
    # Correction / Clarification
    "actually", "but", "however",
    
    # Questions / Requests
    "question", "ask",
    "excuse", "sorry",
    "repeat", "again",
    "help", "what",
    
    # Pause requests
    "hang on", "one second", "just a moment",
])


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_wordlist_from_env(
    env_var: str, 
    default: frozenset[str]
) -> frozenset[str]:
    """Load a wordlist from an environment variable (comma-separated)."""
    if value := os.getenv(env_var):
        return frozenset(w.strip().lower() for w in value.split(",") if w.strip())
    return default


def create_domain_wordlist(
    domain: str,
    additional_ignore: Iterable[str] | None = None,
    additional_interrupt: Iterable[str] | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    """Create domain-specific wordlists with custom additions."""
    ignore = set(DEFAULT_IGNORE_WORDS)
    interrupt = set(DEFAULT_INTERRUPT_WORDS)
    
    if additional_ignore:
        ignore.update(w.lower() for w in additional_ignore)
    
    if additional_interrupt:
        interrupt.update(w.lower() for w in additional_interrupt)
    
    return frozenset(ignore), frozenset(interrupt)
