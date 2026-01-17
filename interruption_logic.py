import re

class InterruptionLogic:

    BACKCHANNEL_WORDS = {
        "yeah", "yea", "ok", "okay",
        "uh", "uhh", "hmm", "mhmm",
        "ok got it", "great", "good",
        "good idea", "sounds good", "cool"
    }

    INTERRUPT_WORDS = {
        "stop", "wait", "hold on", "pause",
        "fine stop", "stop it", "cut it out",
        "enough","halt"
    }

    @classmethod
    def normalize(cls, text: str) -> str:
        # remove punctuation + lowercase
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        return text.strip()

    @classmethod
    def is_backchannel(cls, text: str) -> bool:
        return cls.normalize(text) in cls.BACKCHANNEL_WORDS

    @classmethod
    def is_interrupt(cls, text: str) -> bool:
        return cls.normalize(text) in cls.INTERRUPT_WORDS

    @classmethod
    def is_interruption_required(cls, transcript: str, agent_speaking: bool) -> bool:
        if not agent_speaking:
            return False
        return cls.is_interrupt(transcript)