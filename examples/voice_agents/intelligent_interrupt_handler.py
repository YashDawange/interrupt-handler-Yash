import asyncio
import re

IGNORE_WORDS = {
    "yeah", "yea", "yep",
    "ok", "okay",
    "hmm", "hm",
    "aha",
    "right",
    "uh-huh", "mm-hmm",
}

INTERRUPT_WORDS = {
    "stop", "wait", "pause", "hold on",
    "no", "cancel",
}

def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s'-]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text

def is_only_filler(text: str) -> bool:
    t = normalize(text)
    if not t:
        return True
    return all(w in IGNORE_WORDS for w in t.split())

def has_interrupt_command(text: str) -> bool:
    t = normalize(text)
    for cmd in INTERRUPT_WORDS:
        if re.search(r"\b" + re.escape(cmd) + r"\b", t):
            return True
    return False


class IntelligentInterruptHandler:
    def __init__(self, stt_wait_ms: int = 250):
        self.stt_wait_ms = stt_wait_ms
        self.agent_speaking = False
        self._pending_future: asyncio.Future | None = None

    def set_agent_speaking(self, speaking: bool):
        self.agent_speaking = speaking

    def notify_transcript(self, text: str):
        if self._pending_future and not self._pending_future.done():
            self._pending_future.set_result(text)

    async def decide(self) -> str:
        if self._pending_future is None or self._pending_future.done():
            self._pending_future = asyncio.get_event_loop().create_future()

        text = ""
        try:
            text = await asyncio.wait_for(
                self._pending_future, timeout=self.stt_wait_ms / 1000
            )
        except asyncio.TimeoutError:
            text = ""

        if self.agent_speaking:
            if has_interrupt_command(text):
                return "INTERRUPT"
            if is_only_filler(text):
                return "IGNORE"
            return "INTERRUPT"

        return "RESPOND"
