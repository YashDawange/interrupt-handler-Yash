# livekit-agents/livekit/interrupt_filter.py
import re

class Decision:
    IGNORE = "IGNORE"
    INTERRUPT = "INTERRUPT"
    RESPOND = "RESPOND"
    UNKNOWN = "UNKNOWN"

def normalize_text(text: str) -> str:
    return re.sub(r"[^\w\s'-]", " ", (text or "").lower()).strip()

class InterruptFilter:
    def __init__(self, ignore_words, interrupt_words):
        self.ignore_words = [w.lower() for w in ignore_words]
        self.interrupt_words = [w.lower() for w in interrupt_words]

    def _contains_any(self, text, lst):
        t = normalize_text(text)
        for token in lst:
            tn = normalize_text(token)
            if not tn:
                continue
            # if phrase present anywhere
            if tn in t:
                return True
        return False

    def decide(self, transcript: str, agent_is_speaking: bool) -> str:
        t = (transcript or "").strip()
        if not t:
            return Decision.UNKNOWN

        has_interrupt = self._contains_any(t, self.interrupt_words)
        has_ignore = self._contains_any(t, self.ignore_words)

        if agent_is_speaking:
            if has_interrupt:
                return Decision.INTERRUPT
            if has_ignore and not has_interrupt:
                return Decision.IGNORE
            if has_ignore and has_interrupt:
                return Decision.INTERRUPT
            # default while speaking: ignore short unknowns to avoid choppiness
            return Decision.IGNORE
        else:
            # agent silent -> treat as user input
            return Decision.RESPOND
