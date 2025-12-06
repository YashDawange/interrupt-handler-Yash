from __future__ import annotations

import asyncio
import os
import re
from typing import List, Set

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.agents.voice import (
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
)
from livekit.plugins import deepgram, openai, silero

load_dotenv()


# ----------------------------
# Utility helpers & constants
# ----------------------------

def _split_csv(raw: str) -> List[str]:
    """Split a comma-separated string into normalized tokens."""
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def _split_csv_env(name: str) -> List[str]:
    """Read an env var and split like CSV, return empty list if unset."""
    value = os.getenv(name)
    if not value:
        return []
    return _split_csv(value)


DEFAULT_IGNORE_WORDS = (
    "yeah, ok, okay, k, hmm, mhm, mmm, uh, uh-huh, uh huh, right, yep, yup, sure"
)

DEFAULT_INTERRUPT_COMMANDS = (
    "stop, wait, hold on, one second, just a second, "
    "hang on, please stop, stop talking, no stop"
)

_base_ignore_words: List[str] = _split_csv(DEFAULT_IGNORE_WORDS)
_extra_ignore_words: List[str] = _split_csv_env("IGNORE_WORDS")
IGNORE_WORDS: Set[str] = set(_base_ignore_words + _extra_ignore_words)

_base_interrupt_cmds: List[str] = _split_csv(DEFAULT_INTERRUPT_COMMANDS)
_extra_interrupt_cmds: List[str] = _split_csv_env("INTERRUPT_COMMANDS")
INTERRUPT_COMMANDS_RAW: List[str] = _base_interrupt_cmds + _extra_interrupt_cmds

# build a token-level set from all interrupt phrases
INTERRUPT_TOKENS: Set[str] = set()
for phrase in INTERRUPT_COMMANDS_RAW:
    if phrase:
        for token in phrase.split():
            INTERRUPT_TOKENS.add(token)


def _normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, compress whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_backchannel_utterance(text: str) -> bool:
    """
    Return True if the text is empty or composed only of simple backchannel words
    like 'yeah', 'ok', 'hmm', etc.
    """
    norm = _normalize_text(text)
    if not norm:
        return True
    tokens = norm.split()
    return all(tok in IGNORE_WORDS for tok in tokens)


def has_interrupt_cue(text: str) -> bool:
    """
    Return True if the text contains an explicit interrupt phrase
    or any token from the interrupt commands.
    """
    norm = _normalize_text(text)

    # phrase-level match
    for phrase in INTERRUPT_COMMANDS_RAW:
        if phrase and phrase in norm:
            return True

    # token-level match
    tokens = norm.split()
    return any(tok in INTERRUPT_TOKENS for tok in tokens)


# ----------------------------
# Interruption controller
# ----------------------------

class InterruptionController:
    """
    Manages how user speech interacts with the agent:
    - Backchannels while agent is speaking: ignore & clear turn
    - Backchannels while agent is silent: commit turn (respond)
    - Interrupt commands while speaking: interrupt & commit
    - Interrupt commands while silent: commit (respond)
    - Any other speech while speaking: treat as interrupt & commit
    - Any other speech while silent: commit (respond)
    """

    def __init__(self, session: AgentSession) -> None:
        self.session = session
        self.agent_state: str = "idle"

        # wire up event handlers
        self.session.on("agent_state_changed", self._handle_state_event)
        self.session.on("user_input_transcribed", self._handle_user_transcript_event)

        print("[INTERRUPT] IGNORE_WORDS:", sorted(IGNORE_WORDS))
        print("[INTERRUPT] INTERRUPT_COMMANDS_RAW:", INTERRUPT_COMMANDS_RAW)

    @property
    def is_agent_speaking(self) -> bool:
        return "speaking" in self.agent_state.lower()

    # --- event handlers ---

    def _handle_state_event(self, ev: AgentStateChangedEvent) -> None:
        # support both new_state and state to be robust to SDK versions
        new_state = getattr(ev, "new_state", None)
        if new_state is None:
            new_state = getattr(ev, "state", None)
        self.agent_state = str(new_state)
        print(f"[INTERRUPT] Agent state -> {self.agent_state}")

    def _handle_user_transcript_event(self, ev: UserInputTranscribedEvent) -> None:
        # process transcript asynchronously
        asyncio.create_task(self._process_transcript(ev))

    # --- core logic ---

    async def _process_transcript(self, ev: UserInputTranscribedEvent) -> None:
        # only react to final transcripts
        if not getattr(ev, "is_final", True):
            return

        transcript = (ev.transcript or "").strip()
        if not transcript:
            print("[INTERRUPT] Empty transcript -> clear_user_turn")
            self.session.clear_user_turn()
            return

        print(
            f"[INTERRUPT] Final transcript (speaking={self.is_agent_speaking}): "
            f"{transcript!r}"
        )

        # 1) pure backchannel?
        if is_backchannel_utterance(transcript):
            if self.is_agent_speaking:
                print(
                    "[INTERRUPT] Backchannel while agent SPEAKING "
                    "-> IGNORE & CLEAR TURN"
                )
                self.session.clear_user_turn()
                return
            else:
                print(
                    "[INTERRUPT] Backchannel while agent SILENT "
                    "-> COMMIT user turn (RESPOND)"
                )
                self.session.commit_user_turn()
                return

        # 2) explicit interrupt command?
        if has_interrupt_cue(transcript):
            if self.is_agent_speaking:
                print(
                    "[INTERRUPT] Interrupt cue while agent SPEAKING "
                    "-> INTERRUPT & COMMIT"
                )
                await self.session.interrupt()
                self.session.commit_user_turn()
                return
            else:
                print(
                    "[INTERRUPT] Interrupt cue while agent SILENT "
                    "-> COMMIT user turn (RESPOND)"
                )
                self.session.commit_user_turn()
                return

        # 3) any other speech while agent is speaking is treated as interruption
        if self.is_agent_speaking:
            print(
                "[INTERRUPT] Non-backchannel speech while SPEAKING "
                "-> treat as INTERRUPT & COMMIT"
            )
            await self.session.interrupt()
            self.session.commit_user_turn()
            return

        # 4) normal speech while silent -> just respond
        print("[INTERRUPT] Agent SILENT -> COMMIT user turn (RESPOND)")
        self.session.commit_user_turn()


# ----------------------------
# Agent implementation
# ----------------------------

class ConversationalInterruptAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a friendly, talkative voice assistant. "
                "When you are speaking, small backchannel words like 'yeah', "
                "'ok', or 'hmm' should not interrupt you. "
                "However, if the user says 'stop', 'wait', or similar, "
                "you should immediately stop and listen. "
                "When you are not speaking, treat words like 'yeah', 'ok', or "
                "'hmm' as valid responses."
            )
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Greet the user, then start a short explanation so "
                "interruptions and backchannels can be tested."
            )
        )


# ----------------------------
# Worker entrypoint
# ----------------------------

async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="alloy"),
        turn_detection="manual",
    )

    # attach interruption logic
    InterruptionController(session)

    agent = ConversationalInterruptAgent()

    await session.start(
        agent=agent,
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
