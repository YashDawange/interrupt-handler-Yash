from dataclasses import dataclass
import os


DEFAULT_IGNORE_WORDS = [
    "yeah", "ok", "okay", "yep", "right","hmm", "uh huh", "uh-huh", "mmhmm", "ya", "uh", "ahh",
    "yeah", "ok", "okay", "yep", "yup", "right", "correct", "sure",
    "hmm", "mm-hmm", "mmhmm", "uh-huh", "uh huh", "mhm",
    "uh", "um", "ah", "oh", "er", "erm",
    "cool", "nice", "great", "awesome",
    "gotcha", "got it", "i see", "understood",
    "go on", "carry on", "keep going",
    "absolutely", "definitely", "totally",
    "right", "alright", "fine"
]

DEFAULT_INTERRUPT_WORDS = [
    "stop", "wait", "no", "hold on", "hang on", "pause"
]


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


@dataclass
class InterruptFilter:
    ignore_words: list[str]
    interrupt_words: list[str]

    @classmethod
    def from_env(cls) -> "InterruptFilter":
        ignore_env = os.getenv("IGNORE_WORDS", "")
        interrupt_env = os.getenv("INTERRUPT_WORDS", "")

        ignore_list = (
            [w.strip().lower() for w in ignore_env.split(",") if w.strip()]
            if ignore_env else DEFAULT_IGNORE_WORDS
        )
        interrupt_list = (
            [w.strip().lower() for w in interrupt_env.split(",") if w.strip()]
            if interrupt_env else DEFAULT_INTERRUPT_WORDS
        )

        return cls(ignore_words=ignore_list, interrupt_words=interrupt_list)

    def classify(self, text: str) -> str:
        """Classify transcript as ignore / interrupt / neutral."""
        norm = normalize(text)
        if not norm:
            return "neutral"

        # Direct match for interrupt
        for word in self.interrupt_words:
            if word in norm:
                return "interrupt"

        # All words ignorable → ignore
        words = norm.split()
        if all(w in self.ignore_words for w in words):
            return "ignore"

        return "neutral"
