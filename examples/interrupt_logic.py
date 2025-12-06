# interrupt_logic.py
from enum import Enum
import re


class AgentState(str, Enum):
    SPEAKING = "SPEAKING"
    SILENT = "SILENT"


class Action(str, Enum):
    IGNORE = "IGNORE"
    INTERRUPT = "INTERRUPT"
    RESPOND = "RESPOND"


# Backchannel words that should be ignored while the agent is speaking
IGNORE_WORDS = [
    "yeah",
    "ok",
    "okay",
    "hmm",
    "right",
    "uhhuh",   # from "uh-huh"
    "mmhmm",   # from "mm-hmm"
]

# Words that clearly indicate interruption / correction
INTERRUPT_WORDS = [
    "stop",
    "wait",
    "no",
    "hold",
    "hold on",
    "hang on",
    "pause",
]


def normalize(text: str) -> str:
    """Lowercase + trim spaces."""
    return text.lower().strip()


def clean_and_split(text: str):
    """
    Normalize and split text into tokens. Also removes hyphens so that:
      "uh-huh" -> "uhhuh"
      "mm-hmm" -> "mmhmm"
    """
    text = normalize(text)
    text = re.sub(r"[-]", "", text)       # remove hyphens
    text = re.sub(r"[^\w\s]", "", text)   # remove punctuation
    return text.split()


def is_only_ignore(text: str) -> bool:
    """
    Return True if the entire utterance consists only of IGNORE_WORDS.
    Example:
      "yeah" -> True
      "ok yeah hmm" -> True
      "yeah but" -> False
    """
    tokens = clean_and_split(text)
    if not tokens:
        return False
    return all(token in IGNORE_WORDS for token in tokens)


def contains_interrupt_word(text: str) -> bool:
    """
    Return True if any interrupt keyword appears in the text.
    We check per token after normalization.
    """
    tokens = clean_and_split(text)
    for token in tokens:
        if token in INTERRUPT_WORDS:
            return True
    return False


def decide_action(agent_state: AgentState, user_text: str) -> Action:
    """
    Core logic as per the assignment:

    - If agent is SPEAKING:
        - If user text has interrupt word -> INTERRUPT
        - Else if only ignore words       -> IGNORE
        - Else                            -> INTERRUPT (user says something meaningful)
    - If agent is SILENT:
        - Always RESPOND (even for 'yeah')
    """
    if not user_text.strip():
        return Action.IGNORE

    if agent_state == AgentState.SPEAKING:
        if contains_interrupt_word(user_text):
            return Action.INTERRUPT
        if is_only_ignore(user_text):
            return Action.IGNORE
        return Action.INTERRUPT

    # When agent is not speaking
    return Action.RESPOND
