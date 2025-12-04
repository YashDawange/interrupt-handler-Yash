"""
livekit_agents.interrupt_handler

Decision logic to classify incoming STT text (on VAD events)
into one of: IGNORE / INTERRUPT / RESPOND.
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
    soft_set: Set[str] = set(w.lower() for w in (config.soft_words or []))
    cmd_set: Set[str] = set(w.lower() for w in (config.command_words or []))

    # Command words have the highest priority
    if any(tok in cmd_set for tok in tokens):
        return InterruptionAction.INTERRUPT

    if agent_state == AgentState.SPEAKING:
        # VAD false-start: empty transcript -> IGNORE
        if len(tokens) == 0:
            return InterruptionAction.IGNORE
        # Only soft/backchannel words -> IGNORE
        if all(tok in soft_set for tok in tokens):
            return InterruptionAction.IGNORE
        # Otherwise -> INTERRUPT
        return InterruptionAction.INTERRUPT

    # If agent is silent -> RESPOND
    return InterruptionAction.RESPOND
