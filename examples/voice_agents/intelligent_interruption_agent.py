"""
LiveKit Intelligent Interruption Handling Agent

This agent implements context-aware interruption filtering that distinguishes between
passive acknowledgements (backchanneling) and active interruptions based on:
1. Agent's current speaking state
2. Transcript content analysis
3. Configurable filler word detection

Key Features:
- Ignores filler words (yeah, ok, hmm) when agent is speaking
- Responds to filler words when agent is silent
- Handles mixed inputs (e.g., "yeah but wait" triggers interruption)
- Real-time, imperceptible latency
"""

import asyncio
import logging
import os
import re
from typing import Set

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
)
from livekit.agents.llm import function_tool
from livekit import rtc
from livekit.plugins import silero

logger = logging.getLogger("intelligent-interruption-agent")
logger.setLevel(logging.INFO)

load_dotenv()


# Configurable filler words list (soft inputs that indicate passive listening)
DEFAULT_FILLER_WORDS = {
    # English
    "yeah", "yep", "yes", "yup", "yeah", "yea",
    "ok", "okay", "k",
    "hmm", "hm", "mm", "mmm", "mhm", "mm-hmm", "uh-huh", "uh huh",
    "right", "sure", "alright", "got it",
    "i see", "i understand", "understood",
    "aha", "oh", "ah",

    # Common variations
    "cool", "nice", "great",
    "continue", "go on", "go ahead",
}

# Words that always trigger interruptions (even if mixed with fillers)
INTERRUPTION_KEYWORDS = {
    "wait", "stop", "hold", "hold on", "pause", "no",
    "but", "however", "actually", "question", "what",
    "why", "how", "when", "where", "who",
}


class IntelligentInterruptionHandler:
    """
    Handles intelligent interruption logic based on transcript content and agent state.
    """

    def __init__(
        self,
        session: AgentSession,
        filler_words: Set[str] = None,
        interruption_keywords: Set[str] = None,
        min_words_for_interruption: int = 2,
    ):
        self.session = session
        self.filler_words = filler_words or DEFAULT_FILLER_WORDS
        self.interruption_keywords = interruption_keywords or INTERRUPTION_KEYWORDS
        self.min_words_for_interruption = min_words_for_interruption

        # Track state
        self._agent_was_speaking_on_interrupt = False
        self._last_transcript = ""
        self._pending_resume_task = None

        # Subscribe to state changes
        self.session.on("agent_state_changed", self._on_agent_state_changed)
        self.session.on("user_input_transcribed", self._on_user_input_transcribed)

        logger.info(
            f"Initialized IntelligentInterruptionHandler with "
            f"{len(self.filler_words)} filler words and "
            f"{len(self.interruption_keywords)} interruption keywords"
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison: lowercase, remove punctuation."""
        text = text.lower().strip()
        # Remove punctuation but keep spaces
        text = re.sub(r'[^\w\s]', '', text)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        return text

    def _is_only_filler_words(self, text: str) -> bool:
        """
        Check if the text contains ONLY filler words.
        Returns True if all words in text are filler words.
        """
        if not text:
            return True

        normalized = self._normalize_text(text)
        words = normalized.split()

        if not words:
            return True

        # Check if ALL words are filler words
        for word in words:
            if word and word not in self.filler_words:
                logger.debug(f"Found non-filler word: '{word}'")
                return False

        logger.debug(f"Text contains only filler words: '{text}'")
        return True

    def _contains_interruption_keyword(self, text: str) -> bool:
        """
        Check if text contains any interruption keywords.
        Returns True if ANY interruption keyword is found.
        """
        if not text:
            return False

        normalized = self._normalize_text(text)
        words = normalized.split()

        # Check individual words
        for word in words:
            if word in self.interruption_keywords:
                logger.debug(f"Found interruption keyword: '{word}'")
                return True

        # Check phrases (e.g., "hold on", "i see")
        for phrase in self.interruption_keywords:
            if ' ' in phrase and phrase in normalized:
                logger.debug(f"Found interruption phrase: '{phrase}'")
                return True

        return False

    def _should_ignore_interruption(self, text: str, agent_was_speaking: bool) -> bool:
        """
        Determine if an interruption should be ignored based on:
        1. Agent speaking state when interruption occurred
        2. Transcript content

        Logic Matrix:
        - Agent speaking + only filler words → IGNORE (return True)
        - Agent speaking + contains interruption keywords → ALLOW (return False)
        - Agent silent + any input → ALLOW (return False)
        """
        # If agent was not speaking, process all inputs normally
        if not agent_was_speaking:
            logger.debug("Agent was not speaking, allowing interruption")
            return False

        # Agent was speaking - check transcript content
        if self._contains_interruption_keyword(text):
            logger.info(f"Agent was speaking but user said interruption keyword: '{text}'")
            return False

        if self._is_only_filler_words(text):
            logger.info(f"Agent was speaking and user said only filler words: '{text}' - IGNORING")
            return True

        # If text has meaningful words but no interruption keywords, still allow
        # (conservative approach - user might be trying to say something)
        logger.info(f"Agent was speaking, user said: '{text}' - allowing interruption")
        return False

    def _on_agent_state_changed(self, event):
        """Track when agent starts/stops speaking."""
        logger.debug(f"Agent state changed: {event.old_state} → {event.new_state}")

        # When agent transitions TO speaking, record it
        if event.new_state == "speaking":
            self._agent_was_speaking_on_interrupt = True
        # When agent transitions FROM speaking, clear the flag
        elif event.old_state == "speaking":
            self._agent_was_speaking_on_interrupt = False

    def _on_user_input_transcribed(self, event):
        """
        Handle transcript events and decide whether to ignore/resume interruptions.

        This is called when STT produces interim or final transcripts.
        By this time, VAD has already triggered a pause if agent was speaking.
        Our job: decide if we should immediately resume.

        Note: This must be a synchronous callback. We use asyncio.create_task for async operations.
        """
        text = event.transcript if hasattr(event, 'transcript') else ""
        is_final = event.is_final if hasattr(event, 'is_final') else False

        logger.debug(
            f"User transcript ({'final' if is_final else 'interim'}): '{text}' "
            f"(agent_was_speaking: {self._agent_was_speaking_on_interrupt})"
        )

        # Store the transcript
        self._last_transcript = text

        # Only process if we have text
        if not text or not text.strip():
            return

        # Check if we should ignore this interruption
        should_ignore = self._should_ignore_interruption(
            text,
            self._agent_was_speaking_on_interrupt
        )

        if should_ignore:
            # Agent was speaking and user said only filler words
            # We need to force resume immediately
            logger.info(f"🔇 IGNORING interruption - agent continues speaking")

            # Cancel any pending resume task
            if self._pending_resume_task and not self._pending_resume_task.done():
                self._pending_resume_task.cancel()

            # Schedule immediate resume using create_task
            self._pending_resume_task = asyncio.create_task(self._force_resume())
        else:
            # Valid interruption - let it proceed normally
            logger.info(f"🛑 ALLOWING interruption - user input: '{text}'")

    async def _force_resume(self):
        """
        Force resume the agent's speech immediately.

        This works by leveraging the existing false_interruption resume mechanism,
        but triggering it immediately instead of waiting for the timeout.
        """
        try:
            # Small delay to ensure the interruption has been registered
            await asyncio.sleep(0.05)  # 50ms delay for smoothness

            # Check if audio output supports pause/resume
            audio_output = self.session.output.audio
            if audio_output and audio_output.can_pause:
                # Update agent state back to speaking
                self.session._update_agent_state("speaking")
                # Resume audio playback
                audio_output.resume()
                logger.info("✅ Resumed agent speech successfully")
            else:
                logger.warning("Audio output does not support pause/resume")

        except Exception as e:
            logger.error(f"Error during force resume: {e}", exc_info=True)


class IntelligentInterruptionAgent(Agent):
    """
    Main agent with intelligent interruption handling.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Alex. You are a helpful voice assistant that explains things clearly. "
                "When explaining concepts, you speak in detailed paragraphs to demonstrate the "
                "intelligent interruption handling system. "
                "Keep your responses informative and conversational. "
                "Do not use emojis, asterisks, markdown, or special characters. "
                "You are friendly and patient."
            ),
        )
        self.interruption_handler = None

    async def on_enter(self):
        """Initialize when agent enters the session."""
        # Create the interruption handler
        self.interruption_handler = IntelligentInterruptionHandler(
            session=self.session,
            filler_words=DEFAULT_FILLER_WORDS,
            interruption_keywords=INTERRUPTION_KEYWORDS,
        )

        # Generate initial greeting
        self.session.generate_reply(
            instructions=(
                "Greet the user warmly and introduce yourself. "
                "Explain that you're demonstrating an intelligent interruption handling system. "
                "Tell them they can say 'yeah', 'ok', or 'hmm' while you're speaking and you'll "
                "continue without stopping. But if they say 'wait' or 'stop', you'll pause immediately. "
                "Keep the greeting natural and conversational."
            )
        )

    @function_tool
    async def explain_topic(
        self,
        context: RunContext,
        topic: str,
    ):
        """
        Explain a topic in detail. Used for testing interruption handling.

        Args:
            topic: The topic to explain (e.g., 'artificial intelligence', 'quantum computing')
        """
        logger.info(f"Explaining topic: {topic}")

        # Generate a detailed explanation to demonstrate interruption handling
        return (
            f"I'll explain {topic} in detail. "
            "This will be a longer explanation to demonstrate the interruption handling."
        )

    @function_tool
    async def count_to_number(
        self,
        context: RunContext,
        number: int,
    ):
        """
        Count from 1 to the specified number. Used for testing interruptions.

        Args:
            number: The number to count to (e.g., 10, 20)
        """
        logger.info(f"Counting to {number}")

        # Return the counting sequence
        numbers = ", ".join(str(i) for i in range(1, min(number + 1, 51)))
        return f"Counting: {numbers}"


server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm function to load models before handling requests."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entry point for the agent session."""

    # Set up logging context
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    logger.info(f"Starting intelligent interruption agent in room: {ctx.room.name}")

    # Create agent session with optimized interruption settings
    session = AgentSession(
        # STT: Speech-to-text (the agent's ears)
        stt="deepgram/nova-3",

        # LLM: Large language model (the agent's brain)
        llm="openai/gpt-4o-mini",

        # TTS: Text-to-speech (the agent's voice)
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",

        # VAD: Voice activity detection
        vad=ctx.proc.userdata["vad"],

        # Interruption settings optimized for intelligent handling
        allow_interruptions=True,

        # Short minimum duration to catch all speech
        min_interruption_duration=0.3,  # 300ms

        # Enable false interruption detection with short timeout
        resume_false_interruption=True,
        false_interruption_timeout=0.2,  # 200ms - our custom handler will override this

        # Preemptive generation for lower latency
        preemptive_generation=True,
    )

    # Set up metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage summary: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session
    await session.start(
        agent=IntelligentInterruptionAgent(),
        room=ctx.room,
    )

    logger.info("Intelligent interruption agent session started successfully")


if __name__ == "__main__":
    cli.run_app(server)
