"""
Intelligent Interrupt Handler - Voice Agent Implementation

This agent demonstrates intelligent interruption handling that distinguishes between:
- Passive acknowledgements ("yeah", "ok", "hmm") - IGNORED when agent is speaking
- Active interruptions ("stop", "wait", "no") - ALWAYS processed
- Normal input when agent is silent - ALWAYS processed

SOLUTION APPROACH:
We use `turn_detection="manual"` to disable ALL automatic turn-taking behavior.
This gives us complete control:
- No automatic pauses or interrupts from VAD
- We manually trigger interrupts only for command words ("stop", "wait", etc.)
- We manually trigger responses when appropriate
- Filler words while speaking are completely ignored (no pause, no stutter)

Run this agent the same way as basic_agent.py:
    python intelligent_interrupt_agent.py dev
"""

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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("intelligent-interrupt-agent")


# =============================================================================
# INTERRUPT FILTER - Core filtering logic
# =============================================================================

# Default list of words to ignore when agent is speaking
DEFAULT_IGNORE_WORDS = frozenset([
    # English acknowledgements
    "yeah", "yes", "yep", "yup", "ya",
    "ok", "okay", "k",
    "hmm", "hm", "hmm-hmm", "hmmm",
    "uh-huh", "uh huh", "uhuh", "uhhuh",
    "mm-hmm", "mm hmm", "mmhmm", "mhm",
    "right", "alright",
    "sure", "aha", "ah",
    "i see", "got it", "gotcha",
    "cool", "nice", "great",
    # Common filler sounds
    "um", "uh", "er",
])

# Words that should ALWAYS trigger an interrupt
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


@dataclass
class InterruptAnalysis:
    """Result of analyzing user input for interruption."""
    decision: InterruptDecision
    transcript: str
    agent_was_speaking: bool
    matched_ignore_words: list[str] = field(default_factory=list)
    matched_interrupt_words: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class InterruptFilterConfig:
    """Configuration for the interrupt filter."""
    ignore_words: frozenset[str] = field(default_factory=lambda: DEFAULT_IGNORE_WORDS)
    interrupt_words: frozenset[str] = field(default_factory=lambda: DEFAULT_INTERRUPT_WORDS)
    
    @classmethod
    def from_env(cls) -> "InterruptFilterConfig":
        """Create config from environment variables."""
        ignore_words = DEFAULT_IGNORE_WORDS
        interrupt_words = DEFAULT_INTERRUPT_WORDS
        
        if env_ignore := os.getenv("IGNORE_WORDS"):
            ignore_words = frozenset(w.strip().lower() for w in env_ignore.split(","))
        
        if env_interrupt := os.getenv("INTERRUPT_WORDS"):
            interrupt_words = frozenset(w.strip().lower() for w in env_interrupt.split(","))
        
        return cls(ignore_words=ignore_words, interrupt_words=interrupt_words)


class InterruptFilter:
    """
    Intelligent interrupt filter that distinguishes between passive acknowledgements
    and active interruptions based on agent state and transcript content.
    """
    
    def __init__(self, config: InterruptFilterConfig | None = None):
        self.config = config or InterruptFilterConfig()
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        self._ignore_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in self.config.ignore_words) + r')\b',
            re.IGNORECASE
        )
        self._interrupt_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in self.config.interrupt_words) + r')\b',
            re.IGNORECASE
        )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for analysis."""
        text = ' '.join(text.split())
        text = re.sub(r'[.,!?;:]+', ' ', text)
        return ' '.join(text.split())
    
    def _find_ignore_words(self, text: str) -> list[str]:
        return [m.group() for m in self._ignore_pattern.finditer(text)]
    
    def _find_interrupt_words(self, text: str) -> list[str]:
        return [m.group() for m in self._interrupt_pattern.finditer(text)]
    
    def _is_only_filler(self, text: str) -> bool:
        """Check if text contains only filler/acknowledgement words."""
        normalized = self._normalize_text(text)
        remaining = self._ignore_pattern.sub('', normalized)
        remaining = ' '.join(remaining.split())
        return len(remaining) == 0 or remaining.isspace()
    
    def analyze(self, transcript: str, agent_speaking: bool) -> InterruptAnalysis:
        """Analyze a transcript to determine interrupt behavior."""
        normalized = self._normalize_text(transcript)
        
        ignore_matches = self._find_ignore_words(normalized)
        interrupt_matches = self._find_interrupt_words(normalized)
        
        # Case 1: Agent is NOT speaking - always respond
        if not agent_speaking:
            return InterruptAnalysis(
                decision="respond",
                transcript=transcript,
                agent_was_speaking=False,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason="Agent is silent, treating as valid input"
            )
        
        # Case 2: Agent IS speaking
        
        # 2a: If there are interrupt COMMAND words, always interrupt
        if interrupt_matches:
            return InterruptAnalysis(
                decision="interrupt",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason=f"Found interrupt command words: {interrupt_matches}"
            )
        
        # 2b: If transcript is ONLY filler words, ignore
        if self._is_only_filler(normalized):
            return InterruptAnalysis(
                decision="ignore",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason=f"Only filler words detected: {ignore_matches}"
            )
        
        # 2c: Has substantive content (not just filler) - treat as interrupt
        # This handles cases like "count to 50" while agent is speaking
        return InterruptAnalysis(
            decision="interrupt",
            transcript=transcript,
            agent_was_speaking=True,
            matched_ignore_words=ignore_matches,
            matched_interrupt_words=interrupt_matches,
            reason="Contains substantive content, treating as interrupt"
        )


# =============================================================================
# VOICE AGENT
# =============================================================================

class IntelligentInterruptAgent(Agent):
    """
    Voice agent with intelligent interruption handling.
    
    KEY INSIGHT: Instead of using resume_false_interruption (which causes a brief pause),
    we DISABLE automatic interruptions and manually trigger interrupts ONLY when we 
    detect interrupt command words in the transcript.
    
    This prevents any pause/stutter on filler words like "yeah" or "ok".
    """
    
    def __init__(
        self, 
        interrupt_filter: Optional[InterruptFilter] = None,
        session: Optional[AgentSession] = None,
        **kwargs
    ) -> None:
        instructions = kwargs.pop("instructions", None) or (
            "You are a helpful assistant named Alex. "
            "You provide detailed explanations when asked about topics. "
            "Keep your responses conversational but informative. "
            "When explaining something, give thorough answers. "
            "Do not use emojis, asterisks, or markdown in your responses."
        )
        
        super().__init__(instructions=instructions, **kwargs)
        self._interrupt_filter = interrupt_filter or InterruptFilter(InterruptFilterConfig.from_env())
        self._is_speaking = False
        self._last_speaking_end_time: float = 0
        self._session_ref: Optional[AgentSession] = session
        
    def set_session(self, session: AgentSession) -> None:
        """Set the session reference for manual interrupt control."""
        self._session_ref = session
        
    def on_agent_state_changed(self, old_state: str, new_state: str) -> None:
        """Track agent speaking state."""
        import time
        was_speaking = self._is_speaking
        self._is_speaking = new_state == "speaking"
        
        # Track when agent stopped speaking for grace period
        if was_speaking and not self._is_speaking:
            self._last_speaking_end_time = time.time()
            
        logger.debug(f"Agent state: {old_state} -> {new_state} | Speaking: {self._is_speaking}")
    
    def is_effectively_speaking(self) -> bool:
        """
        Check if agent is speaking OR just stopped (within grace period).
        This prevents race conditions where transcript arrives just as agent stops.
        """
        import time
        if self._is_speaking:
            return True
        # 0.5 second grace period after speaking ends
        # This handles the case where transcript arrives just as agent finishes
        return (time.time() - self._last_speaking_end_time) < 0.5
        
        super().__init__(instructions=instructions, **kwargs)
        self._interrupt_filter = interrupt_filter or InterruptFilter(InterruptFilterConfig.from_env())
        self._is_speaking = False
        self._session_ref: Optional[AgentSession] = session
        
    def set_session(self, session: AgentSession) -> None:
        """Set the session reference for manual interrupt control."""
        self._session_ref = session
        
    def on_agent_state_changed(self, old_state: str, new_state: str) -> None:
        """Track agent speaking state."""
        self._is_speaking = new_state == "speaking"
        logger.debug(f"Agent state: {old_state} -> {new_state} | Speaking: {self._is_speaking}")
    
    def handle_transcript(self, transcript: str) -> InterruptAnalysis:
        """
        Analyze transcript and trigger interrupt if needed.
        
        This is the core of the intelligent interrupt system:
        - If agent is speaking and transcript has interrupt words -> INTERRUPT
        - If agent is speaking and transcript is just filler -> IGNORE (no action needed, audio continues)
        - If agent is NOT speaking -> RESPOND (let LLM handle it normally)
        """
        analysis = self._interrupt_filter.analyze(transcript, agent_speaking=self._is_speaking)
        
        logger.info(
            f"Transcript: '{transcript}' | Speaking: {self._is_speaking} | "
            f"Decision: {analysis.decision} | Reason: {analysis.reason}"
        )
        
        # Only take action on interrupt - manually trigger the interrupt
        if analysis.decision == "interrupt" and self._session_ref is not None:
            current_speech = self._session_ref.current_speech
            if current_speech is not None and not current_speech.interrupted:
                logger.info(f"[MANUAL INTERRUPT] Triggering interrupt for: '{transcript}'")
                # Use force=True because allow_interruptions is False at session level
                current_speech.interrupt(force=True)
        
        return analysis
    
    async def on_enter(self) -> None:
        """Called when agent becomes active."""
        logger.info("Intelligent Interrupt Agent ready!")
        self.session.generate_reply()
    
    @function_tool
    async def tell_long_story(self, context: RunContext) -> str:
        """Tell a long story - good for testing interrupt behavior.
        Use when the user asks for a story or detailed explanation."""
        logger.info("User requested a long story")
        
        return (
            "Let me tell you a fascinating story about the history of computing. "
            "In the early days, computers filled entire rooms and were programmed with punch cards. "
            "The ENIAC, built in 1945, was one of the first general-purpose electronic computers. "
            "It weighed about 27 tons and consumed 150 kilowatts of power. "
            "Interestingly, the term 'bug' in computing came from an actual moth that was found "
            "in a relay of the Harvard Mark II computer in 1947. "
            "Grace Hopper, a pioneering computer scientist, taped the moth into the computer log. "
            "From those massive machines, we've progressed to smartphones that are millions of times "
            "more powerful and fit in our pockets."
        )

    @function_tool
    async def count_slowly(self, context: RunContext, count_to: int = 10) -> str:
        """Count numbers slowly - useful for testing the stop command.
        
        Args:
            count_to: The number to count up to (default: 10)
        """
        logger.info(f"Starting slow count to {count_to}")
        numbers = ", ".join(str(i) for i in range(1, count_to + 1))
        return f"I'll count slowly for you: {numbers}. That's all!"


# =============================================================================
# SERVER SETUP
# =============================================================================

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    """Prewarm the VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model loaded")


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Main entrypoint for the voice agent."""
    
    ctx.log_context_fields = {"room": ctx.room.name}
    
    # Create interrupt filter
    interrupt_filter = InterruptFilter(InterruptFilterConfig.from_env())
    
    # Create session with smart interrupt handling
    # Instead of manual turn detection, we use the framework's built-in handling
    # with min_interruption_words=2 so single filler words don't trigger interrupt
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=ctx.proc.userdata["vad"],
        
        # Enable normal interruption handling
        allow_interruptions=True,
        
        # Require at least 2 words before triggering an interrupt
        # This prevents single-word fillers like "yeah" from interrupting
        min_interruption_words=2,
        
        # Set min duration to filter out very short sounds
        min_interruption_duration=0.5,
        
        # If interrupted, wait for transcript before deciding
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
        
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
    )
    
    # Create the agent with a reference to the session for manual interrupt control
    agent = IntelligentInterruptAgent(interrupt_filter=interrupt_filter)
    agent.set_session(session)
    
    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        agent.on_agent_state_changed(ev.old_state, ev.new_state)
    
    # Track if we've already handled an interrupt for this utterance
    handled_interrupt_for_utterance = {"value": False}
    
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
        """
        Handle both interim and final transcripts.
        
        KEY INSIGHT: We process INTERIM transcripts to detect interrupt commands early!
        When the user says "stop", we don't wait for the final transcript - we interrupt
        immediately when we see the word in an interim transcript.
        
        This solves the timing issue where:
        - Audio triggers VAD check
        - min_interruption_words=2 prevents interrupt for single words
        - By the time final transcript arrives, agent may have finished
        
        With interim processing:
        - User says "stop"
        - Interim transcript arrives with "stop" ~100-200ms later
        - We manually interrupt immediately
        - Agent stops much faster
        """
        if not ev.transcript.strip():
            return
        
        transcript = ev.transcript.strip()
        is_final = ev.is_final
        is_speaking = agent._is_speaking
        
        # Reset interrupt tracking on new utterance (when final arrives)
        if is_final:
            handled_interrupt_for_utterance["value"] = False
        
        # Analyze the transcript
        analysis = agent._interrupt_filter.analyze(transcript, agent_speaking=is_speaking)
        
        # For INTERIM transcripts while agent is speaking:
        # If we detect an interrupt command, manually interrupt immediately!
        if not is_final and is_speaking and analysis.decision == "interrupt":
            if not handled_interrupt_for_utterance["value"]:
                current_speech = session.current_speech
                if current_speech is not None and not current_speech.interrupted:
                    logger.info(f"[EARLY INTERRUPT] Detected '{transcript}' in interim - interrupting now!")
                    current_speech.interrupt(force=True)
                    handled_interrupt_for_utterance["value"] = True
                    return
        
        # For final transcripts, log the decision
        if is_final:
            logger.info(
                f"Transcript: '{transcript}' | Speaking: {is_speaking} | "
                f"Decision: {analysis.decision} | Reason: {analysis.reason}"
            )
            
            if analysis.decision == "ignore":
                logger.info(f"[IGNORED] '{transcript}' - filler word while speaking")
            elif analysis.decision == "interrupt":
                # If we haven't already handled this interrupt via interim
                if not handled_interrupt_for_utterance["value"] and is_speaking:
                    current_speech = session.current_speech
                    if current_speech is not None and not current_speech.interrupted:
                        logger.info(f"[LATE INTERRUPT] '{transcript}' - interrupting via final transcript")
                        current_speech.interrupt(force=True)
                else:
                    logger.info(f"[INTERRUPT] '{transcript}' - reason: {analysis.reason}")
            else:
                logger.info(f"[RESPOND] '{transcript}'")
    
    # Metrics collection
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage() -> None:
        summary = usage_collector.get_summary()
        logger.info(f"Session usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Start the session
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )
    
    logger.info(
        "\n=== Intelligent Interrupt Agent Started ===\n"
        "Using INTERIM TRANSCRIPT processing + min_interruption_words=2:\n"
        "  - Single words like 'yeah', 'ok' won't trigger audio interrupt (less than 2 words)\n"
        "  - Interrupt commands ('stop', 'wait', 'no') detected via INTERIM transcripts\n"
        "  - Manual interrupt triggered immediately when command word detected\n"
        "\n"
        "Test cases:\n"
        "  1. Ask for a story, then say 'yeah' or 'ok' - agent continues\n"
        "  2. Ask agent to count, then say 'stop' - agent stops immediately\n"
        "  3. Wait for agent to finish, then say anything - agent responds\n"
    )


if __name__ == "__main__":
    cli.run_app(server)
