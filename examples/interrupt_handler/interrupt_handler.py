import os
import re
from typing import Iterable, List

try:
    from livekit.agents import (
        AgentSession,
        UserInputTranscribedEvent,
        AgentStateChangedEvent,
    )
except Exception:
    # Allows file to be imported without LiveKit installed (for static checks)
    AgentSession = object  # type: ignore
    UserInputTranscribedEvent = object  # type: ignore
    AgentStateChangedEvent = object  # type: ignore


def _env_list(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [w.strip().lower() for w in raw.split(",") if w.strip()]


IGNORE_WORDS: List[str] = _env_list(
    "INTERRUPT_IGNORE_WORDS",
    "yeah, ok, okay, hmm, uh-huh, right, mhm",
)

INTERRUPT_WORDS: List[str] = _env_list(
    "INTERRUPT_COMMAND_WORDS",
    "stop, wait, hold on, no, cancel",
)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[\\w']+", text.lower())


class AgentStateTracker:
    def __init__(self) -> None:
        self.current = "idle"

    @property
    def is_speaking(self) -> bool:
        return self.current == "speaking"

    def update_from_event(self, ev: AgentStateChangedEvent) -> None:  # type: ignore[valid-type]
        new = getattr(ev, "new_state", None)
        if isinstance(new, str):
            self.current = new


def is_soft_backchannel(text: str, ignore_words: Iterable[str] | None = None) -> bool:
    words = set(ignore_words or IGNORE_WORDS)
    tokens = _tokenize(text)
    return bool(tokens) and all(tok in words for tok in tokens)


def contains_interrupt_command(
    text: str,
    interrupt_words: Iterable[str] | None = None,
) -> bool:
    interrupt_list = [w.lower() for w in (interrupt_words or INTERRUPT_WORDS)]
    tokens = _tokenize(text)
    lowered = " ".join(tokens)

    # single-word commands
    if any(tok in interrupt_list for tok in tokens):
        return True

    # multi-word phrases like "hold on"
    for phrase in interrupt_list:
        if " " in phrase and phrase in lowered:
            return True

    return False


def handle_transcript(
    ev: UserInputTranscribedEvent,  # type: ignore[valid-type]
    session: AgentSession,
    state: AgentStateTracker,
) -> None:
    text = getattr(ev, "transcript", "") or ""
    text = text.strip()
    if not text:
        return

    if not state.is_speaking:
        # Agent is silent → let normal agent logic handle this
        return

    # Agent is speaking
    if is_soft_backchannel(text):
        # Pure backchannel while speaking → ignore completely
        return

    if contains_interrupt_command(text):
        # Hard interruption while speaking → cut off immediately
        try:
            session.interrupt()
        except Exception:
            pass
        return

    # Any other content while speaking is ignored here and can be
    # used later by the normal turn-taking logic if needed.
    return
