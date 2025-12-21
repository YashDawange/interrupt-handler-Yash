import re
from typing import Iterable, Optional

from .. import stt

DEFAULT_BACKCHANNELS = [
    "mm-hmm", "uh-huh", "hmm", "mhm", "hm", "uh", "um", "huh", "mm", "ah", "oh", "eh","mhmm", "mmhmm", "mmm", "aha", "yup", "ya",
    "yeah", "yep", "yes", "yea", "ok", "okay",
    "right", "sure", "alright", "cool", "fine",
    "i see", "got it", "gotcha", "understood",
]

class InterruptionPolicy():
    def __init__(self, backchannels: Optional[list[str]] = None):
        source = backchannels if backchannels is not None else DEFAULT_BACKCHANNELS
        normalized = self.normalize_all(source)
        self._bc_phrases: set[str] = set(normalized)
        self._bc_tokens: set[str] = {p for p in self._bc_phrases if " " not in p}
    
    @staticmethod
    def normalize_text(text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r"[-_]+", " ", t) # Subsituting Hyphens
        t = re.sub(r"[^a-z0-9\s]", "", t) # Drop other punctuation
        t = re.sub(r"(.)\1{2,}", r"\1\1", t) # Keep max 2 repetition
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
        normalized = self.normalize_text(transcript)
        if not normalized:
            return False
        
        if normalized in self._bc_phrases:
            return True
        
        words = normalized.split()
        if not words:
            return False
        
        return all(word in self._bc_tokens for word in words)

    def should_interrupt_now(self, ev: stt.SpeechEvent) -> bool:
        transcript = ev.alternatives[0].text if ev.alternatives else ""
        is_backchannel = self._is_backchannel_only(transcript)
        
        return not is_backchannel

    def is_possible_backchannel(self, text: str) -> bool:
            norm = self.normalize_text(text)
            if not norm: 
                return True 
            
            if norm in self._bc_phrases:
                return True
            
            if len(norm) <= 4: 
                for bc in self._bc_phrases:
                    if bc.startswith(norm):
                        return True
                        
            return False

