from enum import Enum, auto
from typing import Set


class Intent(Enum):
    BACKCHANNEL = auto()
    INTERRUPT = auto()
    START = auto()
    OTHER = auto()


class IntentClassifier:
    """
    Pure intent classifier.
    No agent state. No side effects.
    """

    def __init__(
        self,
        backchannel_words: Set[str],
        interrupt_words: Set[str],
        start_words: Set[str],
    ) -> None:
        self._backchannels = backchannel_words
        self._interrupts = interrupt_words
        self._starts = start_words

    def classify(self, text: str) -> Intent:
        if not text:
            return Intent.OTHER
        for phrase in self._interrupts:
          if phrase in text:
            return Intent.INTERRUPT
          
        for phrase in self._starts:
          if phrase in text:
            return Intent.START
        
        words = text.split()
        if words and all(w in self._backchannels for w in words):
         return Intent.BACKCHANNEL
        
        return Intent.OTHER