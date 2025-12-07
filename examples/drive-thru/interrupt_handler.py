class InterruptHandler:
    def __init__(self):
        self.ignore_list = ["yeah", "ok", "hmm", "uh-huh", "right", "aha"]
        self.interrupt_keywords = ["stop", "wait", "no", "hold"]

    def process_transcript(self, transcript_text: str, agent_is_speaking: bool) -> str:
        text = transcript_text.lower().strip()

        for word in self.interrupt_keywords:
            if word in text:
                return "INTERRUPT"

        if agent_is_speaking and text in self.ignore_list:
            return "IGNORE"

        return "RESPOND"
