import os
import re
import string

def _compile_patterns(env_name: str, defaults: list[str]):
    raw = os.getenv(env_name)
    words = defaults if not raw else [
        w.strip().lower() for w in raw.split(",") if w.strip()
    ]

    words.sort(key=len, reverse=True)

    return [
        re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE)
        for w in words
    ]


class InterruptionLogic:
    def __init__(self):
        self.ignore_patterns = _compile_patterns(
            "INTERRUPT_IGNORE_WORDS",
            [
                "yeah", "ok", "okay", "uh", "uh-huh",
                "hmm", "mhm", "right", "continue", "go on",
            ],
        )

        self.interrupt_patterns = _compile_patterns(
            "INTERRUPT_COMMAND_WORDS",
            [
                "stop", "wait", "hold on",
                "pause", "cancel", "no wait",
            ],
        )

    def _matches(self, patterns, text: str) -> bool:
        return any(p.search(text) for p in patterns)

    def decide(self, text: str) -> str:
        clean = text.lower().translate(
            str.maketrans("", "", string.punctuation)
        )
        clean = " ".join(clean.split())

        if not clean:
            return "IGNORE"

        if self._matches(self.interrupt_patterns, clean):
            return "INTERRUPT"

        if self._matches(self.ignore_patterns, clean):
            return "IGNORE"

        return "RESPOND"
