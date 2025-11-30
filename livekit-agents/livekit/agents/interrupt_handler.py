from __future__ import annotations

from typing import Literal
import string

Decision = Literal["FILLER", "INTERRUPT", "RESPOND"]


class InterruptHandler:
    def __init__(self) -> None:
        # words that are considered "backchannel / filler"
        self.ignore_words: set[str] = {
            "yeah",
            "ok",
            "okay",
            "hmm",
            "right",
            "uh-huh",
            "uh huh",
            "oh",
            "aha",
            "mm-hmm",
            "mm hmm",
        }

        # words that cause a hard interruption
        self.interrupt_words: set[str] = {
            "wait",
            "stop",
            "no",
            "hold on",
        }

    def _normalize(self, text: str) -> str:
        """
        Normalize text for matching:
        - lowercase
        - strip whitespace
        - strip leading/trailing punctuation like '.', ',', '!'
        """
        t = text.lower().strip()
        t = t.strip(string.punctuation)
        return t

    def classify(self, text: str) -> Decision:
        """
        Classify purely based on *content*:
        - FILLER: "yeah", "ok", "oh", etc.
        - INTERRUPT: contains "wait", "stop", "no", "hold on"
        - RESPOND: everything else
        """
        t = self._normalize(text)

        if any(w in t for w in self.interrupt_words):
            return "INTERRUPT"

        if t in self.ignore_words:
            return "FILLER"

        return "RESPOND"
