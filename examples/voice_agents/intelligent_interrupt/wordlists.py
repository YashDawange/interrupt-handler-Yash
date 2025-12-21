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
    # Affirmative responses
    "yeah", "yes", "yep", "yup", "ya",
    "ok", "okay", "k",
    
    # Humming / Thinking sounds
    "hmm", "hm", "hmm-hmm", "hmmm",
    "uh-huh", "uh huh", "uhuh", "uhhuh",
    "mm-hmm", "mm hmm", "mmhmm", "mhm",
    
    # Agreement words
    "right", "alright",
    "sure", "aha", "ah",
    "i see", "got it", "gotcha",
    "cool", "nice", "great",
    
    # Common filler sounds
    "um", "uh", "er",
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
