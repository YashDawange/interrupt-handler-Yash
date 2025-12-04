"""
interrupt_handler.py
Core logic to decide whether to IGNORE / INTERRUPT / RESPOND
based on agent speaking state and a streamed STT transcript.
"""
import re
from dataclasses import dataclass
from typing import List, Set
from enum import Enum

_word_re = re.compile(r"[a-zA-Z]+(?:[-'][a-zA-Z]+)*")

def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _word_re.findall(text or "")]

class AgentState(str, Enum):
    SPEAKING = "speaking"
    SILENT = "silent"

class InterruptionAction(str, Enum):
    IGNORE = "ignore"
    INTERRUPT = "interrupt"
    RESPOND = "respond"

@dataclass
class InterruptionConfig:
    soft_words: List[str]
    command_words: List[str]

def decide_interruption(agent_state: AgentState, user_text: str, config: InterruptionConfig) -> InterruptionAction:
    tokens = _tokenize(user_text)
    soft_set: Set[str] = set(w.lower() for w in config.soft_words or [])
    cmd_set: Set[str] = set(w.lower() for w in config.command_words or [])

    # 1. Command → INTERRUPT
    if any(tok in cmd_set for tok in tokens):
        return InterruptionAction.INTERRUPT

    # 2. Agent is speaking
    if agent_state == AgentState.SPEAKING:
        if len(tokens) == 0:
            return InterruptionAction.IGNORE
        if all(tok in soft_set for tok in tokens):
            return InterruptionAction.IGNORE
        return InterruptionAction.INTERRUPT

    # 3. Silent → RESPOND
    return InterruptionAction.RESPOND
