# interrupt_handler.py

class InterruptionType:
    NONE = "none"             # Normal input → send to LLM
    PASSIVE_ACK = "passive_ack"   # Backchannel while agent speaking → ignore
    ACTIVE_INTERRUPT = "active_interrupt"   # "stop/wait/no" while speaking → interrupt


class InterruptHandler:
    def __init__(self, ignore_words, command_words):
        # normalize words to lowercase for easy matching
        self.ignore_words = set(w.lower() for w in ignore_words)
        self.command_words = set(w.lower() for w in command_words)

        # these will be controlled from the agent side
        self.agent_is_speaking = False      # True while TTS is playing
        self.pending_interruption = False   # True when VAD hears user during TTS

    def classify(self, text: str) -> str:
        """
        Decide how to treat this user utterance.

        Returns one of:
            - InterruptionType.NONE
            - InterruptionType.PASSIVE_ACK
            - InterruptionType.ACTIVE_INTERRUPT
        """
        if not text:
            return InterruptionType.NONE

        normalized = text.lower().strip()
        if not normalized:
            return InterruptionType.NONE

        tokens = normalized.split()

        # 1) If it contains any command word ("stop", "wait", "no", ...)
        #    → treat as active interruption.
        if any(tok in self.command_words for tok in tokens):
            return InterruptionType.ACTIVE_INTERRUPT

        # 2) If agent is speaking & ALL tokens are backchannel / filler
        #    → passive ack, we will ignore this while speaking.
        if self.agent_is_speaking and all(tok in self.ignore_words for tok in tokens):
            return InterruptionType.PASSIVE_ACK

        # 3) Otherwise it's normal user input.
        return InterruptionType.NONE
