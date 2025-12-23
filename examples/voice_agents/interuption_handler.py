
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import (
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
)
from livekit.plugins import silero

# Load environment variables from .env
load_dotenv()

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("intelligent-interrupt-agent")


# =============================================================================
# Interrupt filtering logic
# =============================================================================

# Words that should be ignored if spoken while the agent is talking
DEFAULT_IGNORE_WORDS = frozenset([
    "yeah", "yes", "yep", "yup", "ya",
    "ok", "okay", "k",
    "hmm", "hm", "hmm-hmm", "hmmm",
    "uh-huh", "uh huh", "uhuh", "uhhuh",
    "mm-hmm", "mm hmm", "mmhmm", "mhm", "Mhmm",
    "right", "alright",
    "sure", "aha", "ah",
    "i see", "got it", "gotcha",
    "cool", "nice", "great",
    "um", "uh", "er",
])

# Words that should always stop the agent immediately
DEFAULT_INTERRUPT_WORDS = frozenset([
    "stop", "wait", "hold", "pause",
    "no", "nope", "cancel", "quit",
    "actually", "but", "however",
    "question", "ask",
    "excuse", "sorry",
    "repeat", "again",
    "help", "what",
])

InterruptDecision = Literal["ignore", "interrupt", "respond"]


# Result object returned after analyzing a transcript
@dataclass
class InterruptAnalysis:
    decision: InterruptDecision
    transcript: str
    agent_was_speaking: bool
    matched_ignore_words: list[str] = field(default_factory=list)
    matched_interrupt_words: list[str] = field(default_factory=list)
    reason: str = ""


# Configuration container for interrupt behavior
@dataclass
class InterruptFilterConfig:
    ignore_words: frozenset[str] = field(default_factory=lambda: DEFAULT_IGNORE_WORDS)
    interrupt_words: frozenset[str] = field(default_factory=lambda: DEFAULT_INTERRUPT_WORDS)

    @classmethod
    def from_env(cls) -> "InterruptFilterConfig":
        ignore_words = DEFAULT_IGNORE_WORDS
        interrupt_words = DEFAULT_INTERRUPT_WORDS

        if env_ignore := os.getenv("IGNORE_WORDS"):
            ignore_words = frozenset(w.strip().lower() for w in env_ignore.split(","))

        if env_interrupt := os.getenv("INTERRUPT_WORDS"):
            interrupt_words = frozenset(w.strip().lower() for w in env_interrupt.split(","))

        return cls(ignore_words=ignore_words, interrupt_words=interrupt_words)


# Responsible for deciding whether user speech should be ignored, responded to, or interrupt the agent
class InterruptFilter:
    def __init__(self, config: InterruptFilterConfig | None = None):
        self.config = config or InterruptFilterConfig()
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        self._ignore_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in self.config.ignore_words) + r')\b',
            re.IGNORECASE
        )
        self._interrupt_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in self.config.interrupt_words) + r')\b',
            re.IGNORECASE
        )

    def _normalize_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[.,!?;:]+', ' ', text)
        return ' '.join(text.split())

    def _is_only_filler(self, text: str) -> bool:
        remaining = self._ignore_pattern.sub('', text)
        return not remaining.strip()

    def analyze(self, transcript: str, agent_speaking: bool) -> InterruptAnalysis:
        normalized = self._normalize_text(transcript)

        ignore_matches = self._ignore_pattern.findall(normalized)
        interrupt_matches = self._interrupt_pattern.findall(normalized)

        if not agent_speaking:
            return InterruptAnalysis(
                decision="respond",
                transcript=transcript,
                agent_was_speaking=False,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason="Agent is not speaking"
            )

        if interrupt_matches:
            return InterruptAnalysis(
                decision="interrupt",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason="Explicit interrupt word detected"
            )

        if self._is_only_filler(normalized):
            return InterruptAnalysis(
                decision="ignore",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason="Only filler words"
            )

        return InterruptAnalysis(
            decision="interrupt",
            transcript=transcript,
            agent_was_speaking=True,
            matched_ignore_words=ignore_matches,
            matched_interrupt_words=interrupt_matches,
            reason="Substantive content while speaking"
        )


# =============================================================================
# Voice agent implementation
# =============================================================================

# Main conversational agent that uses the interrupt filter to control speech flow
class IntelligentInterruptAgent(Agent):
    def __init__(
        self,
        interrupt_filter: Optional[InterruptFilter] = None,
        session: Optional[AgentSession] = None,
        **kwargs
    ) -> None:
        instructions = kwargs.pop("instructions", None) or (
            "You are a helpful assistant named Alex. "
            "You provide detailed explanations when asked. "
            "Keep responses conversational and clear."
        )

        super().__init__(instructions=instructions, **kwargs)

        self._interrupt_filter = interrupt_filter or InterruptFilter(
            InterruptFilterConfig.from_env()
        )
        self._is_speaking = False
        self._session_ref: Optional[AgentSession] = session

    # Allows the agent to manually interrupt its own speech
    def set_session(self, session: AgentSession) -> None:
        self._session_ref = session

    # Tracks when the agent starts or stops speaking
    def on_agent_state_changed(self, old_state: str, new_state: str) -> None:
        self._is_speaking = new_state == "speaking"

    # Handles incoming transcripts and triggers interrupts if needed
    def handle_transcript(self, transcript: str) -> InterruptAnalysis:
        analysis = self._interrupt_filter.analyze(
            transcript,
            agent_speaking=self._is_speaking
        )

        if analysis.decision == "interrupt" and self._session_ref:
            current_speech = self._session_ref.current_speech
            if current_speech and not current_speech.interrupted:
                current_speech.interrupt(force=True)

        return analysis

    async def on_enter(self) -> None:
        self.session.generate_reply()

    @function_tool
    async def tell_long_story(self, context: RunContext) -> str:
        return (
            "Here’s a story about the early days of computing. "
            "Early computers filled entire rooms and ran on punch cards. "
            "Over time, they evolved into the devices we carry today."
        )

    @function_tool
    async def count_slowly(self, context: RunContext, count_to: int = 10) -> str:
        return ", ".join(str(i) for i in range(1, count_to + 1))


# =============================================================================
# Server and session wiring
# =============================================================================

# LiveKit agent server
server = AgentServer()


# Preloads the VAD model so startup is faster
def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


# Entry point for each RTC session
@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    interrupt_filter = InterruptFilter(InterruptFilterConfig.from_env())

    session = AgentSession(
        stt="deepgram/nova-2",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2",
        vad=ctx.proc.userdata["vad"],
        allow_interruptions=True,
        min_interruption_words=999,
        min_interruption_duration=0.5,
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
    )

    agent = IntelligentInterruptAgent(interrupt_filter=interrupt_filter)
    agent.set_session(session)

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        agent.on_agent_state_changed(ev.old_state, ev.new_state)

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
        if ev.transcript.strip():
            agent.handle_transcript(ev.transcript)

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)