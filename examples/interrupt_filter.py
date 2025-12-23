import re
import logging

logger = logging.getLogger("interrupt-filter")

class InterruptFilter:
    SOFT_WORDS = {
        "yeah", "yes", "ok", "okay", "hmm", "uh", "uh-huh",
        "right", "yep", "sure", "cool", "got it", "i see", "aha"
    }

    HARD_WORDS = {
        "stop", "wait", "no", "cancel", "pause", "hold",
        "hang on", "shut up", "silence", "quit"
    }

    def normalize(self, text: str) -> set[str]:
        text = re.sub(r"[^a-zA-Z\s]", "", text.lower())
        return set(text.split())

    def is_hard_interrupt(self, text: str) -> bool:
        words = self.normalize(text)
        return bool(words & self.HARD_WORDS)

    def is_soft_only(self, text: str) -> bool:
        words = self.normalize(text)
        if not words:
            return True
        return words.issubset(self.SOFT_WORDS)
