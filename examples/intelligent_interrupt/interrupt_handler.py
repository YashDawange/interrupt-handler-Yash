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
    """
    Logic layer sitting on top of AgentSession.

    Responsibilities:
    - Track whether the agent is currently speaking.
    - Inspect user transcription segments.
    - Decide whether to:
      - IGNORE (backchannel while agent speaking),
      - INTERRUPT (command words or non-soft input while speaking),
      - RESPOND normally (when agent is silent).
    """

    def __init__(self, session):
        self.session = session

        # Configurable word lists (evaluation criterion: easy to change).
        self.ignore_words = _load_word_list(
            "INTERRUPT_IGNORE_WORDS", DEFAULT_IGNORE_WORDS
        )
        self.command_words = _load_word_list(
            "INTERRUPT_COMMAND_WORDS", DEFAULT_COMMAND_WORDS
        )

        # Internal state: is the agent speaking?
        self.agent_speaking = False

        # Hook into session events.
        # NOTE: adapt event names to your repo's actual APIs if needed.
        session.events.on("speech_started", self._on_agent_speech_started)
        session.events.on("speech_stopped", self._on_agent_speech_stopped)
        session.events.on("user_transcription", self._on_user_transcription)

    def _on_agent_speech_started(self, *_args, **_kwargs):
        self.agent_speaking = True

    def _on_agent_speech_stopped(self, *_args, **_kwargs):
        self.agent_speaking = False

    async def _on_user_transcription(self, event):
        """
        Called when there is a (final) STT segment for the user.
        event.text should be the recognized text.
        """
        text = (getattr(event, "text", "") or "").strip().lower()
        if not text:
            return

        words = text.split()
        if not words:
            return

        if self.agent_speaking:
            # Agent is speaking → apply intelligent interruption matrix.

            # 1) If any command word present: INTERRUPT.
            if any(w in self.command_words for w in words):
                await self._interrupt_with_text(text)
                return

            # 2) If all words are in ignore list: IGNORE.
            if all(w in self.ignore_words for w in words):
                # strict requirement: agent must NOT stop/pause/stutter.
                # So do nothing here; let speech continue seamlessly.
                return

            # 3) Mixed or other content: treat as real interruption.
            await self._interrupt_with_text(text)
        else:
            # Agent is silent → always treat as valid input (RESPOND).
            await self._handle_normal_input(text)

    async def _interrupt_with_text(self, text: str):
        """
        Stop ongoing TTS immediately and inject this text as the next user turn.
        """
        # Stop current speech.
        self.session.interrupt()

        # Feed text into the session as user input.
        await self.session.input.set_text(text)
        await self.session.commit_user_turn()

    async def _handle_normal_input(self, text: str):
        """
        Normal behavior when agent is not speaking.
        """
        await self.session.input.set_text(text)
        await self.session.commit_user_turn()
