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


def _parse_csv(value: str) -> List[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _parse_csv_env_optional(name: str) -> List[str]:
    value = os.getenv(name)
    if not value:
        return []
    return _parse_csv(value)


DEFAULT_IGNORE_WORDS = "yeah, ok, okay, k, hmm, mhm, mmm, uh, uh-huh, uh huh, right, yep, yup, sure"

DEFAULT_INTERRUPT_COMMANDS = (
    "stop, wait, hold on, one second, just a second, "
    "hang on, please stop, stop talking, no stop"
)

_base_ignore_words: List[str] = _parse_csv(DEFAULT_IGNORE_WORDS)
_extra_ignore_words: List[str] = _parse_csv_env_optional("IGNORE_WORDS")
IGNORE_WORDS: Set[str] = set(_base_ignore_words + _extra_ignore_words)

_base_interrupt_cmds: List[str] = _parse_csv(DEFAULT_INTERRUPT_COMMANDS)
_extra_interrupt_cmds: List[str] = _parse_csv_env_optional("INTERRUPT_COMMANDS")
INTERRUPT_COMMANDS_RAW: List[str] = _base_interrupt_cmds + _extra_interrupt_cmds

INTERRUPT_TOKENS: Set[str] = {
    token
    for phrase in INTERRUPT_COMMANDS_RAW
    for token in phrase.split()
}


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_backchannel_only(text: str) -> bool:
    norm = _normalize(text)
    if not norm:
        return True
    words = norm.split()
    return all(word in IGNORE_WORDS for word in words)


def contains_interrupt_command(text: str) -> bool:
    norm = _normalize(text)
    for phrase in INTERRUPT_COMMANDS_RAW:
        if phrase and phrase in norm:
            return True
    tokens = norm.split()
    return any(tok in INTERRUPT_TOKENS for tok in tokens)


class IntelligentInterruptionManager:
    def __init__(self, session: AgentSession) -> None:
        self.session = session
        self.agent_state: str = "idle"

        self.session.on("agent_state_changed", self._on_agent_state_changed)
        self.session.on("user_input_transcribed", self._on_user_input_transcribed)

        print("[INTERRUPT-MANAGER] Active IGNORE_WORDS:", sorted(IGNORE_WORDS))
        print("[INTERRUPT-MANAGER] Active INTERRUPT_COMMANDS_RAW:", INTERRUPT_COMMANDS_RAW)

    def _on_agent_state_changed(self, ev: AgentStateChangedEvent) -> None:
        new_state = getattr(ev, "new_state", None)
        if new_state is None:
            new_state = getattr(ev, "state", None)
        self.agent_state = str(new_state)
        print(f"[INTERRUPT-MANAGER] Agent state changed -> {self.agent_state}")

    def _on_user_input_transcribed(self, ev: UserInputTranscribedEvent) -> None:
        asyncio.create_task(self._handle_transcript(ev))

    @property
    def agent_is_speaking(self) -> bool:
        return "speaking" in self.agent_state.lower()

    async def _handle_transcript(self, ev: UserInputTranscribedEvent) -> None:
        if not getattr(ev, "is_final", True):
            return

        transcript = (ev.transcript or "").strip()
        if not transcript:
            print("[INTERRUPT-MANAGER] Empty transcript -> clear_user_turn")
            self.session.clear_user_turn()
            return

        print(
            f"[INTERRUPT-MANAGER] Final transcript "
            f"(speaking={self.agent_is_speaking}): {transcript!r}"
        )

        if is_backchannel_only(transcript):
            if self.agent_is_speaking:
                print(
                    "[INTERRUPT-MANAGER] BACKCHANNEL-only while SPEAKING "
                    "-> IGNORE & CLEAR TURN"
                )
                self.session.clear_user_turn()
                return
            else:
                print(
                    "[INTERRUPT-MANAGER] BACKCHANNEL-only while SILENT "
                    "-> COMMIT user turn (RESPOND)"
                )
                self.session.commit_user_turn()
                return

        if contains_interrupt_command(transcript):
            if self.agent_is_speaking:
                print(
                    "[INTERRUPT-MANAGER] Interrupt command while SPEAKING "
                    "-> INTERRUPT & COMMIT"
                )
                await self.session.interrupt()
                self.session.commit_user_turn()
                return
            else:
                print(
                    "[INTERRUPT-MANAGER] Interrupt command while SILENT "
                    "-> COMMIT user turn (RESPOND)"
                )
                self.session.commit_user_turn()
                return

        if self.agent_is_speaking:
            print(
                "[INTERRUPT-MANAGER] Non-backchannel user speech while SPEAKING "
                "-> treat as INTERRUPT & COMMIT"
            )
            await self.session.interrupt()
            self.session.commit_user_turn()
            return

        print("[INTERRUPT-MANAGER] Agent SILENT -> COMMIT user turn (RESPOND)")
        self.session.commit_user_turn()


class IntelligentInterruptAgent(Agent):
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
                "Greet the user, briefly explain that they can say 'stop' or "
                "'wait' to interrupt you, and then start a short explanation "
                "so interruptions and backchannels can be tested."
            )
        )


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="alloy"),
        turn_detection="manual",
    )

    IntelligentInterruptionManager(session)
    agent = IntelligentInterruptAgent()

    await session.start(
        agent=agent,
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
