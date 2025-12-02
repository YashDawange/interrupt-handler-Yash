# interrupt_handler.py

from enum import Enum, auto
import re
from typing import Iterable


class InterruptionType(Enum):
    NONE = auto()
    PASSIVE_ACK = auto()
    ACTIVE_INTERRUPT = auto()


class InterruptHandler:
    def __init__(
        self,
        passive_ack_words: Iterable[str],
        interrupt_words: Iterable[str],
    ) -> None:
        # normalize to lowercase sets
        self.passive_ack_words = {w.lower() for w in passive_ack_words}
        self.interrupt_words = {w.lower() for w in interrupt_words}

    def _tokenize(self, text: str) -> list[str]:
        # simple word tokenizer: split on non-letters/numbers
        return [t for t in re.split(r"\W+", text.lower()) if t]

    def classify(self, text: str, agent_is_speaking: bool) -> InterruptionType:
        """
        Decide whether this utterance is:
        - PASSIVE_ACK (yeah/ok/hmm etc.)
        - ACTIVE_INTERRUPT (stop/wait/no etc.)
        - NONE (normal content)
        """
        text = (text or "").strip().lower()
        if not text:
            return InterruptionType.NONE

        tokens = self._tokenize(text)

        # 1) If any interrupt word appears anywhere -> ACTIVE_INTERRUPT
        #    e.g. "yeah wait a second" -> ACTIVE_INTERRUPT
        if any(tok in self.interrupt_words for tok in tokens):
            return InterruptionType.ACTIVE_INTERRUPT

        # 2) If agent is speaking AND all words are passive ack words -> PASSIVE_ACK
        #    e.g. "yeah", "ok ok", "uh huh yeah"
        if agent_is_speaking:
            # ignore tokens that aren't in either list (like "the") to be strict
            if all(tok in self.passive_ack_words for tok in tokens):
                return InterruptionType.PASSIVE_ACK

        # 3) Otherwise, treat as normal content
        return InterruptionType.NONE
