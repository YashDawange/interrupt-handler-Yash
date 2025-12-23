import re
from typing import List

IGNORED_WORDS = {
    "uh", "umm", "um", "hmm", "hmmm",
    "haan", "yeah", "ok", "okay",
    "mhm", "uh-huh", "uh huh",
    "right", "aha", "ahaa", "ah",
    "yep", "yup", "sure",
    "gotcha", "got", "it",
    "i", "see", "alright"
}

class InterruptHandler:
    def __init__(self, ignored_words: List[str] = None):
        self.ignored_words = set(ignored_words) if ignored_words else IGNORED_WORDS
        self.agent_speaking = False

    def set_agent_state(self, speaking: bool):
        self.agent_speaking = speaking

    def normalize(self, text: str) -> List[str]:
        text = text.lower()
        print(text)
        text = re.sub(r"[^\w\s]", "", text)
        print(text)

        return text.split()

    def is_filler(self, text: str) -> bool:
        words = self.normalize(text)

        if not words:
            return False

        # 🔥 KEY RULE: very short utterances during agent speech
        if len(words) <= 2 and all(w in self.ignored_words for w in words):
            return True

        return False

    async def handle_interruption(self, text: str, confidence: float = 1.0):
        if self.agent_speaking:
            if confidence < 0.6:
                return "ignored"

            if self.is_filler(text):
                print(f"[IGNORED FILLER] '{text}'")
                return "ignored"

            print(f"[VALID INTERRUPTION] '{text}' → STOP agent")
            return "stop"

        return "process"
