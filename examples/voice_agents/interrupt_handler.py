# examples/voice_agents/interrupt_handler.py
"""
Interrupt handling logic for LiveKit intelligent interruption challenge.

Functions:
- classify_input(user_text: str) -> 'IGNORE'|'INTERRUPT'|'RESPOND'
- should_interrupt(user_text: str, agent_speaking: bool) -> bool

Configuration:
- IGNORE_WORDS and INTERRUPT_KEYWORDS can be customized using environment variables:
  INTERRUPT_IGNORE_LIST (comma-separated)
  INTERRUPT_KEYWORDS_LIST (comma-separated)

Defaults:
  IGNORE_WORDS = ['yeah','ok','hmm','right','uh-huh','mm','mm-hmm','uh']
  INTERRUPT_KEYWORDS = ['stop','wait','no','hold','hold on','pause','cancel','stop that','stop now']
"""

import os
import re
from typing import List

def _load_list_from_env(var_name: str, default: List[str]) -> List[str]:
    v = os.getenv(var_name, "").strip()
    if not v:
        return default
    # split by comma and strip whitespace, lower-case
    items = [x.strip().lower() for x in v.split(",") if x.strip()]
    return items or default

# Configurable lists (can be set in .env or environment)
IGNORE_WORDS: List[str] = _load_list_from_env(
    "INTERRUPT_IGNORE_LIST",
    ["yeah", "ok", "hmm", "right", "uh-huh", "mm", "mm-hmm", "uh", "aha"],
)

INTERRUPT_KEYWORDS: List[str] = _load_list_from_env(
    "INTERRUPT_KEYWORDS_LIST",
    ["stop", "wait", "no", "hold", "hold on", "pause", "cancel", "stop that", "stop now"],
)

# Precompile word-boundary regex for multi-word interrupt phrases
_interrupt_phrase_patterns = [re.compile(r"\b" + re.escape(p) + r"\b") for p in INTERRUPT_KEYWORDS]

def _tokenize(text: str) -> List[str]:
    # split on whitespace and punctuation
    return re.findall(r"\w+(?:[-']\w+)?", text.lower())

def contains_interrupt_phrase(text: str) -> bool:
    """Return True if the text contains any interrupt keyword/phrase."""
    t = text.lower()
    for pat in _interrupt_phrase_patterns:
        if pat.search(t):
            return True
    # fallback: check token-level interrupt words
    tokens = _tokenize(text)
    return any(tok in INTERRUPT_KEYWORDS for tok in tokens)

def contains_only_ignore_words(text: str) -> bool:
    """Return True if text contains only ignore words (possibly repeated)."""
    tokens = _tokenize(text)
    if not tokens:
        return False
    return all(tok in IGNORE_WORDS for tok in tokens)

def classify_input(user_text: str) -> str:
    """
    Classify user input semantically.
    Returns:
      - 'INTERRUPT' if input contains interrupt keywords/phrases.
      - 'IGNORE' if input is only backchannel/ack words.
      - 'RESPOND' otherwise (meaningful input).
    """
    if not user_text or not user_text.strip():
        return "RESPOND"  # empty typed input -> treat as normal input

    normalized = user_text.strip().lower()

    # If contains explicit interrupt phrase -> INTERRUPT
    if contains_interrupt_phrase(normalized):
        return "INTERRUPT"

    # If it's only filler/backchannel words -> IGNORE
    if contains_only_ignore_words(normalized):
        return "IGNORE"

    # Mixed or meaningful content -> RESPOND (and while speaking may be interrupt)
    return "RESPOND"

def should_interrupt(user_text: str, agent_speaking: bool) -> bool:
    """
    Return True if we should interrupt the agent (stop speaking) based on user_text and agent state.

    Logic:
      - If agent is speaking:
          * If classify_input == 'INTERRUPT' => True
          * If classify_input == 'IGNORE' => False
          * If classify_input == 'RESPOND' => False (we treat meaningful non-command while speaking as ignored to prevent false stops)
            NOTE: This choice follows strict requirement: while speaking, filler must not stop. Mixed inputs containing interrupt keywords already caught above.
      - If agent is silent:
          * We should process the input (i.e., treat as an interruption to start a response) -> return True
    """
    cls = classify_input(user_text)
    if agent_speaking:
        if cls == "INTERRUPT":
            return True
        # While speaking, only explicit interrupt keywords cause interruption.
        return False
    else:
        # Agent silent => treat all user inputs as valid to respond to
        return True
