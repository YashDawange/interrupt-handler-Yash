IGNORE_WORDS = {"yeah", "ok", "okay", "hmm", "uh-huh"}
STOP_WORDS = {"stop", "wait", "no", "pause"}

class InterruptHandler:
    def __init__(self):
        self.agent_speaking = False

    def set_agent_speaking(self, value):
        self.agent_speaking = value

    def should_interrupt(self, text):
        words = text.lower().split()

        if not self.agent_speaking:
            return True

        if any(w in STOP_WORDS for w in words):
            return True

        if all(w in IGNORE_WORDS for w in words):
            return False

        return True
