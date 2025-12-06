import re
from .base_engine import BaseEngine

class RulesEngine(BaseEngine):
    def __init__(self, ignore_words, interrupt_words):
        self.ignore = {self._norm(w) for w in ignore_words if w}
        self.interrupt = [self._norm(w) for w in interrupt_words if w]

    def _norm(self, s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip())

    async def classify(self, transcript: str, agent_is_speaking: bool, context: dict = None) -> dict:
        text = self._norm(transcript or "")
        
        # 1. Check Hard Interrupts (Highest Priority)
        for cmd in self.interrupt:
            if cmd and (cmd in text):
                return {"decision": "INTERRUPT", "score": 1.0, "reason": "keyword_match"}

        # 2. Check Passive Ignore (Only if agent is speaking)
        if agent_is_speaking:
            tokens = [t for t in re.split(r"\s+", text) if t]
            # Heuristic: Short sentence + all words are in ignore list
            if len(tokens) <= 4 and all(self._norm(tok) in self.ignore for tok in tokens):
                return {"decision": "IGNORE", "score": 0.95, "reason": "passive_filler"}

        # 3. Default
        return {"decision": "NORMAL", "score": 0.0, "reason": "default"}