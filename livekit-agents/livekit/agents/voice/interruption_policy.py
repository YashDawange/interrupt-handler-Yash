import re
from enum import Enum
from typing import Iterable, Optional

from .. import stt

class State(Enum):
    IDLE = 0 # No action to perform
    PENDING = 1 # Waiting for STT
    RESET = 2 # Do not commit turn

DEFAULT_BACKCHANNELS = [
    "mm-hmm","uh-huh","hmm","mhm","hm","uh","um","mm","ah","oh","eh",
    
    "yeah","yep","yes","yea","ok", "okay",
    
    "right","sure","alright","cool","fine",
    
    "i see","got it","gotcha","understood",
]


class InterruptionPolicy():
    def __init__(self, backchannels_override: Optional[list[str]] = None):
        self.state = State.IDLE
        
        if backchannels_override is not None:
            source = backchannels_override
        else:
            source = DEFAULT_BACKCHANNELS
        
        normalized = self.normalize_all(normalized)

        self._bc_phrases: set[str] = set(normalized)
        self._bc_tokens: set[str] = {p for p in self._bc_phrases if " " not in p}

    @staticmethod
    def normalize_text(text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r"[-_]+", " ", t) # Subsituting Hyphens
        t = re.sub(r"[^a-z0-9\s]", "", t) # Drop other punctuation
        t = re.sub(r"\s+", " ", t).strip() # Change multiple whitespace to single whitespace

        return t

    @classmethod
    def normalize_all(cls, items: Iterable[str]) -> list[str]:
        out: list[str] = []
        for x in items:
            nx = cls.normalize_text(x)
            if nx:
                out.append(nx)
        return out

    def _is_backchannel_only(self, transcript: str) -> bool:
        text = self.normalize_text(transcript)
        if not text:
            return False

        if text in self._bc_phrases:
            return True

        words = text.split()

        if not words:
            return False
        
        for word in words:
            if word not in self._bc_tokens:
                return False

        return True

    def should_interrupt_now(self, ev: stt.SpeechEvent) -> bool:
        if self.state != State.PENDING:
            return False

        transcript = ev.alternatives[0].text if ev.alternatives else ""
        if self._is_backchannel_only(transcript):
            self.state = State.RESET
            return False

        self.state = State.IDLE
        return True

    def should_commit_turn(self, final_transcript: Optional[str] = None) -> bool:
        if final_transcript is not None and self._is_backchannel_only(final_transcript):
            self.state = State.IDLE
            return False

        if self.state == State.RESET:
            self.state = State.IDLE
            return False

        return True

    def change_state_pending(self) -> None:
        self.state = State.PENDING
