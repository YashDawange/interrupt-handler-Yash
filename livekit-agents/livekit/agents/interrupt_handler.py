from enum import Enum
from typing import Set


class AgentState(Enum):
    SPEAKING = "speaking"
    SILENT = "silent"


class InterruptionDecision(Enum):
    IGNORE = "ignore"
    INTERRUPT = "interrupt"
    RESPOND = "respond"


IGNORE_WORDS: Set[str] = {
    "yeah",
    "yes",
    "ok",
    "okay",
    "hmm",
    "uh",
    "uh-huh",
    "right",
}

INTERRUPT_WORDS: Set[str] = {
    "stop",
    "wait",
    "no",
    "pause",
    "hold on",
}


def contains_interrupt_command(text: str) -> bool:
    text = text.lower()
    return any(word in text for word in INTERRUPT_WORDS)


def decide_interruption(
    agent_state: AgentState,
    transcript: str,
) -> InterruptionDecision:
    text = transcript.lower().strip()

    if agent_state == AgentState.SPEAKING:
        if contains_interrupt_command(text):
            return InterruptionDecision.INTERRUPT

        if text in IGNORE_WORDS:
            return InterruptionDecision.IGNORE

        return InterruptionDecision.INTERRUPT

    return InterruptionDecision.RESPOND
from enum import Enum
from typing import Set


class AgentState(Enum):
    SPEAKING = "speaking"
    SILENT = "silent"


class InterruptionDecision(Enum):
    IGNORE = "ignore"
    INTERRUPT = "interrupt"
    RESPOND = "respond"


IGNORE_WORDS: Set[str] = {
    "yeah",
    "yes",
    "ok",
    "okay",
    "hmm",
    "uh",
    "uh-huh",
    "right",
}

INTERRUPT_WORDS: Set[str] = {
    "stop",
    "wait",
    "no",
    "pause",
    "hold on",
}


def contains_interrupt_command(text: str) -> bool:
    text = text.lower()
    return any(word in text for word in INTERRUPT_WORDS)


def decide_interruption(
    agent_state: AgentState,
    transcript: str,
) -> InterruptionDecision:
    text = transcript.lower().strip()

    if agent_state == AgentState.SPEAKING:
        if contains_interrupt_command(text):
            return InterruptionDecision.INTERRUPT

        if text in IGNORE_WORDS:
            return InterruptionDecision.IGNORE

        return InterruptionDecision.INTERRUPT

    return InterruptionDecision.RESPOND
