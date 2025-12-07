from enum import Enum
from typing import Literal

class AgentSpeechState(Enum):
    SPEAKING = "speaking"
    SILENT = "silent"  # includes listening / idle / thinking for our purposes


Decision = Literal["IGNORE", "INTERRUPT", "RESPOND"]

# Words that are PURE backchannels (we ignore while speaking)
IGNORE_WORDS = {
    "yeah",
    "ya",
    "ok",
    "okay",
    "k",
    "hmm",
    "hmmm",
    "right",
    "uh-huh",
    "uh",
    "aha",
    "mhm",
    "mm-hmm",
    "mm",
    "yep",
    "yup",
    "sure",
    "got it",
    "gotcha",
    "alright",
    "all right",
}

# Words / phrases that should interrupt immediately
INTERRUPT_WORDS = {
    "stop",
    "wait",
    "hold",
    "hold on",
    "no",
    "pause",
    "cancel",
    "nevermind",
    "never mind",
}


def classify_user_text(text: str, agent_state: AgentSpeechState) -> Decision:
    """
    Decide how to treat a user utterance, given the current agent speech state.

    - While SPEAKING:
        * pure soft words ("yeah", "ok", ...)      -> IGNORE
        * anything else ("no stop", "yeah wait")   -> INTERRUPT
    - While SILENT:
        * everything (including "yeah")            -> RESPOND
    """
    normalized = text.lower().strip()
    if not normalized:
        return "IGNORE"

    tokens = normalized.split()

    # If there is any interrupt word anywhere -> INTERRUPT
    if any(tok in INTERRUPT_WORDS for tok in tokens) or any(
        phrase in normalized for phrase in INTERRUPT_WORDS
    ):
        return "INTERRUPT"

    # Is the utterance purely backchannel?
    all_soft = all(tok in IGNORE_WORDS for tok in tokens)

    if agent_state == AgentSpeechState.SPEAKING:
        # Agent is talking:
        # - purely soft backchannels -> IGNORE
        # - anything richer -> treat as real interruption
        if all_soft:
            return "IGNORE"
        else:
            return "INTERRUPT"
    else:
        # Agent is silent:
        # Everything is valid input (including "yeah")
        return "RESPOND"
