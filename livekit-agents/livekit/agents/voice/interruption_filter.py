"""Interruption filter module for intelligent filler word detection.

This module provides functionality to distinguish between passive backchanneling
(which should be ignored) and active interruptions (which should be processed)
during voice agent conversations.

The core algorithm filters out common filler words like "yeah", "ok", "uh-huh"
to prevent premature interruption of agent speech.

Example:
    >>> from livekit.agents.voice.interruption_filter import should_interrupt, get_filler_words
    >>> filler_words = get_filler_words()
    >>> should_interrupt("yeah", filler_words)
    False
    >>> should_interrupt("stop talking", filler_words)
    True
"""

from __future__ import annotations

import os
import string
from functools import lru_cache

__all__ = [
    "FILLER_WORDS",
    "should_interrupt",
    "get_filler_words",
    "load_filler_words",
    "normalize_text",
]

# Default filler words that represent passive backchanneling.
# These are common listener acknowledgments that should not interrupt agent speech.
# Includes multiple variations to handle different STT transcription patterns.
FILLER_WORDS: set[str] = {
    # Affirmative responses
    "yeah",
    "yep",
    "yup",
    "yes",
    "yea",
    "ya",
    "yah",
    "ye",
    # Negative responses (backchanneling)
    "no",
    "nah",
    "nope",
    # OK variations
    "ok",
    "okay",
    "okey",
    "okie",
    "okey-dokey",
    "okie-dokie",
    "kay",
    "k",
    # Uh-huh variations (different transcription patterns)
    "uh-huh",
    "uh huh",
    "uhhuh",
    "uhuh",
    "uh-uh",
    # Hesitation sounds
    "uh",
    "um",
    "er",
    "ah",
    "oh",
    # Hmm variations
    "mhm",
    "mm-hmm",
    "mmhmm",
    "mm hmm",
    "mmm",
    "hmm",
    "hm",
    "huh",
    # Aha variations
    "aha",
    "a-ha",
    # Agreement/acknowledgment
    "right",
    "sure",
    "got it",
    "gotcha",
    "i see",
    "alright",
    "alrighty",
    "aight",
    "fine",
    "good",
    "great",
    "nice",
    "cool",
    "true",
    "exactly",
    "absolutely",
    "definitely",
    "certainly",
    "totally",
    "understood",
    "interesting",
    # Continuation prompts (passive)
    "go on",
    "go ahead",
    "continue",
    # Interjections
    "wow",
    "oh wow",
    "oh ok",
    "oh okay",
    "really",
    "seriously",
}


def load_filler_words() -> set[str]:
    """Load filler words from environment variable or return defaults.

    Checks the `FILLER_WORDS_OVERRIDE` environment variable for a comma-separated
    list of custom filler words. If set, these replace the default filler words.
    Otherwise, returns a copy of the default FILLER_WORDS set.

    Returns:
        A set of filler words to use for interruption filtering.

    Example:
        >>> import os
        >>> os.environ["FILLER_WORDS_OVERRIDE"] = "custom,words"
        >>> load_filler_words()
        {'custom', 'words'}
    """
    override = os.environ.get("FILLER_WORDS_OVERRIDE")
    if override:
        return {word.strip().lower() for word in override.split(",") if word.strip()}
    return FILLER_WORDS.copy()


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing, stripping whitespace, and removing punctuation.

    This preprocessing step ensures consistent matching against filler words
    regardless of case or punctuation in the original transcription.
    Hyphens are preserved as they appear in filler words like "uh-huh".

    Args:
        text: The raw transcription text to normalize.

    Returns:
        Normalized text suitable for filler word matching.

    Example:
        >>> normalize_text("Yeah!")
        'yeah'
        >>> normalize_text("  OK, sure...  ")
        'ok sure'
        >>> normalize_text("uh-huh")
        'uh-huh'
    """
    text = text.lower().strip()
    # Remove punctuation but preserve hyphens (used in words like "uh-huh")
    punctuation_to_remove = string.punctuation.replace("-", "")
    text = text.translate(str.maketrans("", "", punctuation_to_remove))
    return text


@lru_cache(maxsize=1)
def get_filler_words() -> frozenset[str]:
    """Get cached filler words set.

    Loads filler words once on first call and caches the result for subsequent
    calls. Uses frozenset to enable LRU caching.

    Returns:
        A frozen set of filler words for use with should_interrupt().

    Note:
        The cache is application-wide. To use different filler words,
        pass them directly to should_interrupt() instead.
    """
    return frozenset(load_filler_words())


def should_interrupt(transcription: str, filler_words: set[str] | frozenset[str]) -> bool:
    """Determine if a transcription should trigger an interruption.

    This function implements the core filler word filtering algorithm to
    distinguish passive backchanneling from genuine interruptions.

    Algorithm:
        1. Handle empty/whitespace-only input → return False
        2. Normalize transcription (lowercase, strip, remove punctuation)
        3. Remove multi-word filler phrases first (e.g., "got it", "i see")
        4. Tokenize into single words
        5. Remove single-word fillers from token list
        6. If non-filler words remain → return True (interrupt)
        7. If only filler words → return False (ignore)

    Args:
        transcription: The user's speech transcription to analyze.
        filler_words: Set of filler words/phrases to ignore.

    Returns:
        True if the transcription should trigger an interruption,
        False if it contains only filler words and should be ignored.

    Example:
        >>> filler_words = get_filler_words()
        >>> should_interrupt("yeah", filler_words)
        False
        >>> should_interrupt("yeah ok mhm", filler_words)
        False
        >>> should_interrupt("stop", filler_words)
        True
        >>> should_interrupt("yeah but wait", filler_words)
        True
    """
    # Handle empty or whitespace-only input
    if not transcription or not transcription.strip():
        return False

    normalized = normalize_text(transcription)

    # Handle case where normalization results in empty string
    if not normalized:
        return False

    # Check for multi-word filler phrases first (process longer phrases first)
    text_to_check = normalized
    for filler in sorted(filler_words, key=len, reverse=True):
        if " " in filler:  # Multi-word filler phrase
            text_to_check = text_to_check.replace(filler, " ")

    # Tokenize remaining text into single words
    words = text_to_check.split()

    # Remove single-word fillers
    non_filler_words = [w for w in words if w not in filler_words]

    # If any non-filler words remain, this is a genuine interruption
    return len(non_filler_words) > 0
