import os
from typing import List

DEFAULT_IGNORE_WORDS = ["yeah", "ok", "okay", "hmm", "uh-huh", "right"]
DEFAULT_COMMAND_WORDS = ["wait", "stop", "no"]

def _load_word_list(env_name: str, default: List[str]) -> List[str]:
    value = os.getenv(env_name)
    if not value:
        return default
    return [w.strip().lower() for w in value.split(",") if w.strip()]

class InterruptHandler:
    def __init__(self, session):
        self.session = session
        self.ignore_words = _load_word_list("INTERRUPT_IGNORE_WORDS", DEFAULT_IGNORE_WORDS)
        self.command_words = _load_word_list("INTERRUPT_COMMAND_WORDS", DEFAULT_COMMAND_WORDS)
        self.agent_speaking = False

        # ✅ Exact LiveKit Agents events
        self.session.on("agent_state_changed", self._on_agent_state_changed)
        self.session.on("user_input_transcribed", self._on_user_transcription)

    def _on_agent_state_changed(self, event):
        if hasattr(event, 'new_state'):
            self.agent_speaking = (event.new_state == "speaking")

    async def _on_user_transcription(self, event):
        text = (getattr(event, 'transcript', '') or '').strip().lower()
        if not text:
            return

        words = text.split()
        if not words:
            return

        if self.agent_speaking:
            # Speaking + command word → INTERRUPT
            if any(w in self.command_words for w in words):
                await self._interrupt_with_text(text)
                return
            
            # Speaking + only ignore words → IGNORE (continue seamlessly)
            if all(w in self.ignore_words for w in words):
                return
            
            # Speaking + mixed/other → INTERRUPT
            await self._interrupt_with_text(text)
        else:
            # Silent → normal input
            await self._handle_normal_input(text)

    async def _interrupt_with_text(self, text: str):
        self.session.interrupt()
        # Feed text as user turn (exact API may vary slightly)
        await self.session.say(f"User interrupted: {text}", add_to_chat_ctx=True)

    async def _handle_normal_input(self, text: str):
        await self.session.say(f"Heard: {text}", add_to_chat_ctx=True)
