IGNORE_WORDS = {
    "yeah", "ya", "yep", "ok", "okay", "hmm", "uh-huh", "mm", "huh"
}

INTERRUPT_WORDS = {
    "stop", "wait", "hold on", "pause", "dont", "don't", "no-no"
}

import asyncio

class InterruptHandler:
    def __init__(self):
        self._buffer = asyncio.Queue(maxsize=4)

    async def push_transcript(self, text: str):
        """Gets called for every STT interim or final transcript."""
        try:
            self._buffer.put_nowait(text.lower().strip())
        except asyncio.QueueFull:
            pass

    async def decide(self, agent_is_speaking: bool) -> str:
        """
        Called when VAD detects user SPEECH_START.
        Returns one of:
          - "ignore"
          - "interrupt"
          - "user_input"
        """

        collected = []
        try:
            while True:
                item = self._buffer.get_nowait()
                collected.append(item)
        except:
            pass

        if not collected:
            # no transcript = user started speaking = interrupt!
            return "interrupt" if agent_is_speaking else "user_input"

        all_text = " ".join(collected)

        # speaking → ignore backchannel
        if agent_is_speaking:
            # HARD interruption
            if any(w in all_text for w in INTERRUPT_WORDS):
                return "interrupt"

            # ONLY ignore words → ignore
            tokens = all_text.split()
            if all(t in IGNORE_WORDS for t in tokens):
                return "ignore"

            # Anything else → interrupt
            return "interrupt"

        # not speaking: treat everything as user input
        return "user_input"
