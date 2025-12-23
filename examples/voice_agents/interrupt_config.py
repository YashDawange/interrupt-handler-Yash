import os
import re

# Default backchannel and interrupt words can be overridden via env vars:
#   BACKCHANNEL_WORDS="yeah, ok, okay, hmm, uh-huh"
#   INTERRUPT_WORDS="stop, wait, no, cancel"
_DEFAULT_BACKCHANNEL_WORDS = {
    "ah",    "aha",
    "hm",    "hmm",
    "mhm",    "mhmm",
    "mm-hmm",    "mmhmm",
    "uh-huh",    "um",
    "uh",    "uhhuh",
    "absolutely",    "exactly",
    "indeed",    "right",
    "sure",    "true",
    "understood",    "correct",
    "definitely",    "alright",
    "cool",    "fine",
    "nice",    "ok",
    "okay",    "yeah",
    "yep",    "yes",
    "yup",    "sounds good",
    "go on",    "got it",
    "i see",    "makes sense",
    "keep going",    "tell me more",
    "really",    "wow",
    "for real",    "seriously",
    "interesting",    "no way",
}

_DEFAULT_INTERRUPT_WORDS = {
    "stop", "wait", "no", "hold", "cancel", "pause",
    "enough", "hold on",

    # strong interrupts
    "quit", "abort", "end", "terminate",
    "cut it", "cut", "shut up",

    # clarification interrupts
    "listen", "sorry", "excuse me",
    "one second", "just a second", "a second",

    # correction-style interrupts
    "not that", "that's wrong", "incorrect",
    "i meant", "let me explain",

    # conversational interrupts
    "hang on", "wait up", "hold up",
    "back up", "go back",

    # caps variants (ASR sometimes preserves case)
    "STOP", "WAIT", "NO", "CANCEL", "PAUSE",
}



def _parse_word_list(env_name: str, default: set[str]) -> set[str]:
    raw = os.getenv(env_name)
    if not raw:
        return default
    return {w.strip().lower() for w in raw.split(",") if w.strip()}


BACKCHANNEL_WORDS = _parse_word_list("BACKCHANNEL_WORDS", _DEFAULT_BACKCHANNEL_WORDS)
INTERRUPT_WORDS = _parse_word_list("INTERRUPT_WORDS", _DEFAULT_INTERRUPT_WORDS)


def _normalize_tokens(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower()) if t]


def is_soft_backchannel(text: str) -> bool:
    tokens = _normalize_tokens(text)
    if not tokens:
        return False
    return all(tok in BACKCHANNEL_WORDS for tok in tokens)


def contains_strong_interrupt(text: str) -> bool:
    tokens = _normalize_tokens(text)
    return any(tok in INTERRUPT_WORDS for tok in tokens)
