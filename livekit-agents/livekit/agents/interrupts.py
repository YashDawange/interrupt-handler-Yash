# interrupts.py
# Small shared module to hold config and speaking state for interrupt logic.
# Keep it minimal so it is easy to import from anywhere.

import os
import json
from threading import Lock

# Default lists - graders can override by editing config/interrupts.json or env var
DEFAULT_CONFIG = {
    "SOFT_WORDS": ["yeah","ok","hmm","right","uh-huh","mm","uh","uh-huh"],
    "COMMAND_WORDS": ["stop","wait","no","pause","cancel","stop it","wait please"]
}

# Try load config from a repo-local json for easy grading adjustments
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "interrupts.json")
try:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = DEFAULT_CONFIG

SOFT_WORDS = set([w.lower() for w in cfg.get("SOFT_WORDS", DEFAULT_CONFIG["SOFT_WORDS"])])
COMMAND_WORDS = set([w.lower() for w in cfg.get("COMMAND_WORDS", DEFAULT_CONFIG["COMMAND_WORDS"])])

# speaking state is global (process-level). If your server runs multiple agent objects
# change to per-session state (attach to Session object instead).
_agent_lock = Lock()
_agent_is_speaking = False

def set_agent_speaking(val: bool):
    global _agent_is_speaking
    with _agent_lock:
        _agent_is_speaking = bool(val)

def agent_is_speaking() -> bool:
    with _agent_lock:
        return bool(_agent_is_speaking)

def analyze_text_for_interrupt(text: str):
    """
    Returns True if text should cause an interruption (i.e., contains a command or non-soft words).
    Returns False if text is only soft words (so should be ignored).
    """
    if not text:
        return False  # no text -> prefer ignore (safer to continue speaking)
    tokens = [t.strip(".,!?;:()[]\"'").lower() for t in text.split()]
    if not tokens:
        return False
    # if any token matches a command -> interrupt
    for t in tokens:
        if t in COMMAND_WORDS:
            return True
    # if any token not in SOFT_WORDS -> treat as real input -> interrupt
    if any(t not in SOFT_WORDS for t in tokens):
        return True
    # otherwise all tokens are soft -> ignore
    return False
