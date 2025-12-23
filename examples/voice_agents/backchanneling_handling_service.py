from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Set

from livekit.agents import AgentSession, AgentStateChangedEvent, UserInputTranscribedEvent
import asyncio

@dataclass
class BackchannelingConfig:
    """
    Configuration for semantic interruption handling.

    - ignore_words: words that are treated as passive acknowledgements
      when the agent is speaking.
    - interrupt_words: words that explicitly signal a real interruption.
    """
    #words are store in a set for instant loopkup to reduce latency
    ignore_words: Set[str] = field(
        default_factory=lambda: {
            "yeah",
            "ya",
            "yep",
            "yup",
            "ok",
            "okay",
            "k",
            "mm",
            "hmm",
            "uh",
            "uhh",
            "uh-huh",
            "right",
            "sure",
            "aha",
            "mmm",
        }
    )
    interrupt_words: Set[str] = field(
        default_factory=lambda: {
            "stop",
            "wait",
            "hold",
            "no",
            "nope",
            "pause",
            "enough",
            "cancel",
        }
    )


class BackchannelingHandlingService:
    """
    High-level logic layer sitting *on top* of LiveKit's VAD/turn detection.

    Requirements implemented:

    1. If agent is speaking & user says ONLY filler (yeah/ok/hmm):
       - Do NOT interrupt the agent.
       - Do NOT commit this as a user turn (clear it).

    2. If agent is speaking & user says anything containing an interrupt
       word (e.g. "yeah wait a second", "no stop"):
       - Interrupt immediately (semantic interruption).

    3. If agent is NOT speaking:
       - Do not interfere. "Yeah" is treated like a normal answer and
         flows into the usual LLM pipeline.
    """

    def __init__(self, session: AgentSession, config: BackchannelingConfig | None = None) -> None:
        self._session = session
        self._config = config or BackchannelingConfig()
        self._agent_is_speaking: bool = False

        self._wire_events()


    # Event wiring
    def _wire_events(self) -> None:
        @self._session.on("agent_state_changed")
        def _on_agent_state_changed(ev):
            self._agent_is_speaking = ev.new_state == "speaking"

        @self._session.on("user_input_transcribed")
        def _on_user_input_transcribed(ev):
            # Must be sync – spawn async logic if needed
            asyncio.create_task(self._handle_user_transcript(ev))

    async def _handle_user_transcript(self, ev) -> None:
        transcript = (ev.transcript or "").strip().lower()
        if not transcript:
            return

        # if agent is not speaking then treat user input normally 
        if not self._agent_is_speaking:
            return

        tokens = self._normalize_tokens(transcript)

        # checking for interrupt words in partial transcript to improve latency
        # VAD is faster than SST, and waiting for SST to generate the entire transcript of user
        # will lead to latency 
        if not ev.is_final:
            if self._is_confident_interrupt(tokens):
                self._session.interrupt(force=True)
            return

        if self._contains_interrupt_word(tokens):
            self._session.interrupt(force=True)
            return

        if self._is_soft_ack_only(tokens):
            self._session.clear_user_turn()
    


    # Core logic
    def _is_confident_interrupt(self, tokens: list[str]) -> bool:
        for t in tokens:
            for w in self._config.interrupt_words:
                #for exact match only
                if t == w:
                    return True
        return False

    def _normalize_tokens(self, text: str) -> list[str]:
        cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
        tokens = [t for t in cleaned.split() if t]
        return tokens

    def _is_soft_ack_only(self, tokens: Iterable[str]) -> bool:
        """
        True if every token is in ignore_words. Mixed sentences like
        "yeah wait" will return False (because "wait" is not ignored).
        """
        toks = list(tokens)
        if not toks:
            return False
        ignore = self._config.ignore_words
        return all(t in ignore for t in toks)

    def _contains_interrupt_word(self, tokens: Iterable[str]) -> bool:
        interrupt = self._config.interrupt_words
        return any(t in interrupt for t in tokens)

    def _handle_while_agent_speaking(self, transcript: str) -> None:
        tokens = self._normalize_tokens(transcript)

        # 1) Mixed or pure interruption: "wait", "no stop", "yeah wait a sec"
        if self._contains_interrupt_word(tokens):
            # Semantic interruption – forcefully stop agent speech.
            # This uses the official interrupt API on AgentSession.
            self._session.interrupt(force=True)
            # We *do not* clear the user turn here; the text should be
            # processed by the LLM as a normal "stop" / "wait" request.
            return

        # 2) Soft acknowledgement only: "yeah", "ok", "hmm"
        if self._is_soft_ack_only(tokens):
            # Clear the transcription/audio buffer so the "yeah" turn is
            # discarded and won't be processed when agent finishes.
            self._session.clear_user_turn()
            return

        # 3) Anything else while agent is speaking – treat as a real
        #    interruption by default (safer than ignoring).
        self._session.interrupt(force=True)
