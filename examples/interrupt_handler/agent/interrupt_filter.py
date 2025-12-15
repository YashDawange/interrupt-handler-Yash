# agent/interrupt_filter.py
import os
import re
from typing import List

DEFAULT_IGNORE = ["yeah", "ok", "hmm", "uh-huh", "right", "uh-huh", "uhhuh", "uhh"]
DEFAULT_INTERRUPT = ["stop", "wait", "no", "hold", "hold on", "wait a second", "wait a sec", "pause"]

def _load_list_from_env(env_name: str, fallback: List[str]) -> List[str]:
    val = os.getenv(env_name, "")
    if not val:
        return fallback
    return [w.strip().lower() for w in val.split(",") if w.strip()]

IGNORE_LIST = _load_list_from_env("INTERRUPT_IGNORE_LIST", DEFAULT_IGNORE)
INTERRUPT_LIST = _load_list_from_env("INTERRUPT_WORDS_LIST", DEFAULT_INTERRUPT)

# Prepare regexes to match whole words / short phrases
def _compile_patterns(words):
    # escape and sort descending length to match multi-word phrases first
    words_sorted = sorted(set(words), key=lambda x: -len(x))
    patterns = [re.compile(r"\b" + re.escape(w) + r"\b", flags=re.IGNORECASE) for w in words_sorted]
    return patterns

IGNORE_PATTERNS = _compile_patterns(IGNORE_LIST)
INTERRUPT_PATTERNS = _compile_patterns(INTERRUPT_LIST)

def contains_ignore_word(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    for p in IGNORE_PATTERNS:
        if p.search(text):
            return True
    return False

def contains_interrupt_word(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    for p in INTERRUPT_PATTERNS:
        if p.search(text):
            return True
    return False

def is_mixed_input(text: str) -> bool:
    # Mixed input: contains both an ignore token and an interrupt token
    return contains_interrupt_word(text) and contains_ignore_word(text)

def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())
