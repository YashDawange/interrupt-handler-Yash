# interrupt_handler.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, List

from livekit.agents import (
    AgentSession,
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
)
from livekit.agents import stt as stt_mod


@dataclass
class InterruptConfig:
    """
    Configuration for context-aware interruption handling.

    - ignore_words: words that should NOT interrupt the agent while it is speaking
    - command_words: words that SHOULD interrupt, even if they appear inside
      a longer sentence.
    """
    ignore_words: Set[str] = field(
        default_factory=lambda: {
            "yeah",
            "ya",
            "ok",
            "okay",
            "hmm",
            "uh-huh",
            "uhhuh",
            "mm-hmm",
            "mmhmm",
            "right",
            "aha",
        }
    )
    command_words: Set[str] = field(
        default_factory=lambda: {
            "stop",
            "wait",
            "hold",
            "hold on",
            "no",
            "cancel",
            "pause",
        }
    )


class ContextAwareSTT:
    """
    Wrapper around a real STT implementation (e.g. Deepgram).

    Responsibilities:
    - Expose the same interface AgentSession expects for STT:
        * label
        * capabilities
        * aclose()
        * recognize()
        * stream()
    - Listen to AgentSession events to know whether the agent is speaking.
    - When the agent is speaking:
        * filler only ("yeah", "ok", "hmm") -> ignore / drop user turn
        * contains command ("stop", "wait", "no") -> actively interrupt
    """

    def __init__(
        self,
        base_stt: stt_mod.STT,
        config: Optional[InterruptConfig] = None,
    ) -> None:
        self._base = base_stt
        self._config = config or InterruptConfig()

        self._session: Optional[AgentSession] = None
        self._agent_speaking: bool = False

    # ------------------------------------------------------------------
    # Wiring from myagent.py
    # ------------------------------------------------------------------
    def set_session(self, session: AgentSession) -> None:
        """
        Attach to the AgentSession so we can:
        - Track when the agent is speaking.
        - Inspect user transcripts and decide whether to ignore them.
        """
        self._session = session

        @session.on("agent_state_changed")
        def _on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
            # states: "initializing", "idle", "listening", "thinking", "speaking"
            self._agent_speaking = ev.new_state == "speaking"

        @session.on("user_input_transcribed")
        def _on_user_input(ev: UserInputTranscribedEvent) -> None:
            self._handle_transcript(ev)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------
    def _handle_transcript(self, ev: UserInputTranscribedEvent) -> None:
        """
        Decide whether the current user transcript should:
        - be treated as a real interruption, or
        - be ignored because it's just backchanneling ("yeah", "ok", ...)

        Rules:
        - If the agent is NOT speaking:
            * "yeah / ok" are normal inputs. Do nothing special.
        - If the agent IS speaking:
            * if text has a command word -> call session.interrupt()
            * elif text is ONLY ignore words -> clear user turn
            * else -> treat as normal interruption / input
        """
        if self._session is None:
            return

        # We only want to react when the STT result is final,
        # not on partial streaming hypotheses.
        if not getattr(ev, "is_final", False):
            return

        text = (ev.transcript or "").strip().lower()
        if not text:
            return

        tokens: List[str] = [
            t.strip(".,!?")
            for t in text.split()
            if t.strip(".,!?")
        ]
        if not tokens:
            return

        token_set = set(tokens)

        # Case 1: Agent is NOT speaking
        # -> "yeah/ok/hmm" can be legitimate answers. Leave it alone.
        if not self._agent_speaking:
            return

        # Case 2: Agent IS speaking

        # 2a) Contains command word -> explicit interruption, even if short.
        if token_set & self._config.command_words:
            # Force an interruption of the current TTS segment.
            # The user text ("stop", "wait", etc.) will remain
            # as the current user turn and be processed.
            self._session.interrupt()
            return

        # 2b) Only soft backchannel words -> ignore this as a turn.
        all_soft = all(tok in self._config.ignore_words for tok in token_set)

        if all_soft:
            # Remove this input from the current user turn so the LLM
            # never sees it as a message.
            self._session.clear_user_turn()
            return

        # 2c) Anything else (e.g. "okay I disagree with that") should be
        # treated as a real interruption / input. Let the session handle it.

    # ------------------------------------------------------------------
    # STT interface: delegate everything to underlying STT
    # ------------------------------------------------------------------
    @property
    def label(self) -> str:
        return self._base.label

    @property
    def capabilities(self) -> stt_mod.STTCapabilities:
        return self._base.capabilities

    async def aclose(self) -> None:
        await self._base.aclose()

    async def recognize(self, *args, **kwargs):
        return await self._base.recognize(*args, **kwargs)

    def stream(self, *args, **kwargs):
        # We don't touch the audio stream; all smart behavior
        # is based on session events.
        return self._base.stream(*args, **kwargs)
