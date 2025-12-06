import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Set

from livekit.agents import (
    AgentSession,
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
)


def _load_word_list_from_env(env_var: str, default: Iterable[str]) -> Set[str]:
    raw = os.getenv(env_var)
    if not raw:
        return {w.strip().lower() for w in default if w.strip()}
    return {w.strip().lower() for w in raw.split(",") if w.strip()}


@dataclass
class BackchannelInterruptionHandler:
    """
    Handles the logic matrix:

    - "yeah / ok / hmm" while speaking  -> IGNORE (no break)
    - "wait / stop / no" while speaking -> INTERRUPT (stop immediately)
    - "yeah / ok / hmm" while silent    -> RESPOND as confirmation
    """

    session: AgentSession
    ignore_words: Set[str] = field(default_factory=set)
    command_words: Set[str] = field(default_factory=set)

    _agent_state: str = "initializing"

    def __post_init__(self) -> None:
        if not self.ignore_words:
            self.ignore_words = _load_word_list_from_env(
                "BACKCHANNEL_IGNORE_WORDS",
                [
                    "yeah",
                    "ya",
                    "yep",
                    "yup",
                    "ok",
                    "okay",
                    "k",
                    "mm",
                    "hmm",
                    "u",
                    "uh",
                    "huh"
                    "mm-hmm",
                    "uh-huh",
                    "uh huh",
                    "right",
                    "gotcha",
                    "got it",
                    "i see",
                    "sure",
                    "alright",
                    "mhmm",
                    "mmm",
                ],
            )

        if not self.command_words:
            self.command_words = _load_word_list_from_env(
                "BACKCHANNEL_COMMAND_WORDS",
                [
                    "stop",
                    "wait",
                    "hold",
                    "hold on",
                    "pause",
                    "no",
                    "hang on",
                    "cancel",
                    "enough",
                ],
            )

    def attach(self) -> None:
        @self.session.on("agent_state_changed")
        def _on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
            self._agent_state = getattr(ev, "new_state", self._agent_state)

        @self.session.on("user_input_transcribed")
        def _on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
            text = ev.transcript or ""
            if not text.strip():
                return
            self._handle_transcript(text, is_final=ev.is_final)

    # ------------ core logic ------------ #

    def _normalize(self, text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"[^a-z0-9'\s]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _handle_transcript(self, raw_text: str, is_final: bool) -> None:
        text = self._normalize(raw_text)
        if not text:
            return

        tokens = text.split()
        if not tokens:
            return

        contains_command = any(tok in self.command_words for tok in tokens)
        all_tokens_ignored = all(tok in self.ignore_words for tok in tokens)

        agent_speaking = self._agent_state == "speaking"

        # ---------- CASE 1: Agent is SPEAKING ---------- #
        if agent_speaking:
            # Interrupt as soon as we hear a command (even on partial)
            if contains_command:
                self._interrupt_for_command()
                return

            # Pure backchannel (yeah/ok/hmm) -> swallow ONLY on final
            if is_final and all_tokens_ignored:
                self._swallow_backchannel_while_speaking()
                return

            # Final non-command non-backchannel → treat as interruption too
            if is_final and not all_tokens_ignored:
                self._interrupt_for_command()
                return

            # non-final non-command: wait for more audio
            return

        # ---------- CASE 2: Agent is SILENT ---------- #
        if is_final and all_tokens_ignored:
            # Treat "yeah / ok / hmm" as confirmation answer
            self.session.generate_reply(
                instructions=(
                    f"User said '{raw_text}'. Treat this as a confirmation "
                    f"and continue with the next step."
                )
            )
            return

        # Anything else while silent is handled by normal agent logic.

    # ------------ helper behaviors ------------ #

    def _swallow_backchannel_while_speaking(self) -> None:
        try:
            self.session.clear_user_turn()
        except Exception:
            pass

    def _interrupt_for_command(self) -> None:
        """
        Stop current speech immediately and DO NOT start a new reply.
        We just stop and wait for whatever the user says next.
        """
        try:
            # hard stop current speech + LLM stream
            self.session.interrupt(force=True)
        except Exception:
            pass

        # Clear current user turn so "stop / wait" is not processed as a new query
        try:
            self.session.clear_user_turn()
        except Exception:
            pass
