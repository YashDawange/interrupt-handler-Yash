import asyncio
import logging
import re

logger = logging.getLogger("interrupt-handler")

FILLER_WORDS = {
    "uh", "um", "hmm", "hm", "yeah", "yes", "yep", "okay", "ok",
    "right", "uhh", "huh", "mm", "mmm"
}

STOP_WORDS = {
    "stop", "cancel", "wait", "pause", "shut up", "hold on"
}


def is_filler(text: str) -> bool:
    text = text.lower()
    text = re.sub(r"[^a-z\s]", "", text)
    words = text.split()

    if not words:
        return True

    return all(w in FILLER_WORDS for w in words)


class InterruptHandler:
    def __init__(self, session):
        self.session = session
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def handle(self, text: str):
        cleaned = text.strip()

        if not cleaned:
            return

        # 1. Ignore fillers COMPLETELY
        if is_filler(cleaned):
            logger.info(f"Ignored filler: {cleaned}")
            return

        # 2. Stop commands interrupt immediately
        lowered = cleaned.lower()
        if any(word in lowered for word in STOP_WORDS):
            logger.info("Stop command detected")
            await self._stop()
            return

        # 3. Real user intent → interrupt + respond
        await self._stop()

        reply = await self._llm(cleaned)
        await self._speak(reply)

    async def _speak(self, text: str):
        async with self._lock:
            self._task = asyncio.create_task(self._run(text))

    async def _run(self, text: str):
        handle = None
        try:
            handle = await self.session.say(text)
            await handle.wait_finished()
        except asyncio.CancelledError:
            if handle:
                try:
                    handle.cancel()
                except:
                    pass
        finally:
            self._task = None

    async def _stop(self):
        async with self._lock:
            if self._task:
                self._task.cancel()
                self._task = None

    async def _llm(self, text: str) -> str:
        completion = await self.session.llm.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.4,
        )
        return completion.choices[0].message.content


SYSTEM_PROMPT = """
You are a real-time voice assistant.

Behavior rules:
- Completely ignore filler utterances like: uh, um, hmm, yeah, okay.
- Do not acknowledge them.
- Do not pause or restart your speech if they occur.
- If the user says stop, cancel, wait, pause, or shut up: immediately stop speaking.
- Only respond when the user expresses real intent.
- Be clear, concise, and helpful.
"""
