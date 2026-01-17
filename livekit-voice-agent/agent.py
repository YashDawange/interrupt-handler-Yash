from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Iterable

from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import Agent, AgentServer, AgentSession, room_io
from livekit.plugins import noise_cancellation, silero

try:
    # NOTE: This is the canonical import used by LiveKit examples.
    from livekit.plugins.turn_detector.multilingual import MultilingualModel  # type: ignore[import-not-found]
except Exception as exc:  # pragma: no cover
    MultilingualModel = None  # type: ignore[assignment]
    _TURN_IMPORT_ERROR = exc
else:
    _TURN_IMPORT_ERROR = None


load_dotenv(".env.local")
load_dotenv()  # allow fallback to .env


logger = logging.getLogger("assignment-logic")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@dataclass(frozen=True)
class Settings:
    log_level: str
    stats_every_n: int
    ignored_tokens: frozenset[str]
    ignored_phrases: frozenset[str]
    interrupt_tokens: frozenset[str]
    interrupt_phrases: frozenset[str]

    @staticmethod
    def _parse_csv(value: str) -> list[str]:
        return [part.strip().lower() for part in value.split(",") if part.strip()]

    @classmethod
    def from_env(cls) -> "Settings":
        ignored_raw = os.getenv(
            "IGNORED_WORDS",
            "yeah,ok,okay,hmm,aha,uh-huh,right,yup,yep,sure,correct,gotcha,i see",
        )
        interrupt_raw = os.getenv("INTERRUPT_WORDS", "stop,wait,no")
        stats_every_n = int(os.getenv("STATS_EVERY_N", "25"))
        log_level = os.getenv("LOG_LEVEL", "INFO")

        ignored_items = cls._parse_csv(ignored_raw)
        interrupt_items = cls._parse_csv(interrupt_raw)

        ignored_phrases = frozenset([x for x in ignored_items if " " in x])
        ignored_tokens = frozenset([x for x in ignored_items if " " not in x])
        interrupt_phrases = frozenset([x for x in interrupt_items if " " in x])
        interrupt_tokens = frozenset([x for x in interrupt_items if " " not in x])

        return cls(
            log_level=log_level,
            stats_every_n=max(0, stats_every_n),
            ignored_tokens=ignored_tokens,
            ignored_phrases=ignored_phrases,
            interrupt_tokens=interrupt_tokens,
            interrupt_phrases=interrupt_phrases,
        )


_PUNCT_DELETE = {
    ord("."): None,
    ord(","): None,
    ord("!"): None,
    ord("?"): None,
    ord(";"): None,
    ord(":"): None,
    ord("\""): None,
    ord("'"): None,
}


def normalize_text(text: str) -> str:
    # Fast hot-path normalization: lower + punctuation delete + trim.
    # Avoid regex to keep per-segment overhead low.
    return text.lower().translate(_PUNCT_DELETE).strip()


def _all_in(items: Iterable[str], allowed: frozenset[str]) -> bool:
    for item in items:
        if item not in allowed:
            return False
    return True


class Action(str, Enum):
    IGNORE = "ignore"
    INTERRUPT = "interrupt"
    RESPOND = "respond"


@dataclass
class Stats:
    committed: int = 0
    ignored: int = 0
    interrupted: int = 0
    responded: int = 0
    last_log_at: float = 0.0

    def maybe_log(self, *, every_n: int) -> None:
        if every_n <= 0:
            return
        if self.committed % every_n != 0:
            return
        now = time.monotonic()
        # prevent log spam if multiple commits land on same tick
        if now - self.last_log_at < 0.5:
            return
        self.last_log_at = now
        logger.info(
            "stats committed=%d ignored=%d interrupted=%d responded=%d",
            self.committed,
            self.ignored,
            self.interrupted,
            self.responded,
        )


class DecisionEngine:
    def __init__(self, settings: Settings):
        self._ignored_tokens = settings.ignored_tokens
        self._ignored_phrases = settings.ignored_phrases
        self._interrupt_tokens = settings.interrupt_tokens
        self._interrupt_phrases = settings.interrupt_phrases

    def decide(self, *, normalized_text: str, is_speaking: bool) -> Action:
        if not normalized_text:
            return Action.IGNORE if is_speaking else Action.RESPOND

        # Phrase-level checks first to handle multi-word items like "i see".
        if is_speaking:
            if normalized_text in self._interrupt_phrases:
                return Action.INTERRUPT
            if normalized_text in self._ignored_phrases:
                return Action.IGNORE

        tokens = normalized_text.split()

        if is_speaking:
            for token in tokens:
                if token in self._interrupt_tokens:
                    return Action.INTERRUPT

            # Backchannel/filler: require *all* tokens to be in ignored list.
            if _all_in(tokens, self._ignored_tokens):
                return Action.IGNORE

            return Action.INTERRUPT

        return Action.RESPOND


@lru_cache(maxsize=1)
def get_vad():
    return silero.VAD.load()


@lru_cache(maxsize=1)
def get_turn_model():
    if MultilingualModel is None:
        raise ImportError(
            "Could not import MultilingualModel from livekit.plugins.turn_detector. "
            "Ensure `livekit-agents[turn-detector]` is installed."
        ) from _TURN_IMPORT_ERROR
    return MultilingualModel()

class AssignmentAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a context-aware Voice Assistant designed for a strict university assignment.
            
            # CRITICAL RULES
            1. WHEN SPEAKING: Ignore backchannel words (Yeah, Ok, Hmm, Right). Do NOT pause. Keep talking.
            2. WHEN SPEAKING: Stop IMMEDIATELY if the user says "Stop", "Wait", or "No".
            3. WHEN SILENT: Respond to "Yeah" or "Ok" as a normal conversation turn.
            
            # PERSONALITY
            Professional, precise, and concise (1-3 sentences). No special formatting.
            """
        )

server = AgentServer()

@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    settings = Settings.from_env()
    _configure_logging(settings.log_level)
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    decision_engine = DecisionEngine(settings)
    stats = Stats()

    # --- YOUR REQUESTED STRUCTURE (UNCHANGED) ---
    session = AgentSession(
        stt="deepgram/nova-2:en-IN",          # Your requested model string
        llm="openai/gpt-4o-mini",             # Your requested model string
        tts="deepgram/aura-2:athena",         # Your requested model string
        vad=get_vad(),
        turn_detection=get_turn_model(),
    )

    # --- THE STRICT LOGIC LAYER ---
    @session.on("user_speech_committed")
    def _on_user_speech_committed(msg: rtc.TranscriptionSegment):
        stats.committed += 1
        normalized = normalize_text(msg.text)
        action = decision_engine.decide(normalized_text=normalized, is_speaking=session.is_speaking)

        if session.is_speaking:
            if action == Action.IGNORE:
                stats.ignored += 1
                logger.info("Context: [SPEAKING] | Input: '%s' -> ACTION: IGNORE (No Hiccup)", normalized)
                stats.maybe_log(every_n=settings.stats_every_n)
                return
            if action == Action.INTERRUPT:
                stats.interrupted += 1
                logger.info("Context: [SPEAKING] | Input: '%s' -> ACTION: INTERRUPT (Active Command)", normalized)
                stats.maybe_log(every_n=settings.stats_every_n)
                session.interrupt()
                return
            # Fallback safety.
            stats.maybe_log(every_n=settings.stats_every_n)
            return

        # Context: SILENT.
        stats.responded += 1
        logger.info("Context: [SILENT] | Input: '%s' -> ACTION: RESPOND", normalized)
        stats.maybe_log(every_n=settings.stats_every_n)

    # Start the agent (BVC is safe for your environment)
    await session.start(
        room=ctx.room,
        agent=AssignmentAgent(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVC(),
            ),
        ),
    )

    # --- THE CRITICAL FIX ---
    # allow_interruptions=False disables the "hiccup".
    # The agent will ONLY stop if your logic above calls session.interrupt().
    await session.generate_reply(
        instructions="Introduce yourself with a long, detailed sentence about how robust your logic is. Explicitly ask the user to say 'Right' or 'Yep' while you are talking to prove you won't stop.",
        allow_interruptions=False 
    )

if __name__ == "__main__":
    agents.cli.run_app(server)