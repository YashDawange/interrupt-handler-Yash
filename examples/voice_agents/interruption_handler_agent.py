"""
Intelligent Interruption Handler Agent

This example demonstrates context-aware interruption handling that distinguishes
between passive acknowledgements (backchanneling) and active interruptions.

The agent ignores backchanneling words (yeah, ok, hmm) when speaking, but
responds to them when silent. It always interrupts for actual commands (wait, stop, no).
"""

import logging
import os
import re
from typing import TYPE_CHECKING

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
from livekit.agents.llm.tool_context import StopResponse
from livekit.agents.voice.events import (
    AgentFalseInterruptionEvent,
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

if TYPE_CHECKING:
    from livekit.agents.voice.agent_session import AgentSession

logger = logging.getLogger("interruption-handler-agent")

load_dotenv()


class InterruptionHandler:
    """Handles intelligent interruption filtering based on agent state and transcript content."""

    def __init__(
        self,
        *,
        backchanneling_words: list[str] | None = None,
        interruption_words: list[str] | None = None,
    ) -> None:
        """Initialize the interruption handler.

        Args:
            backchanneling_words: List of words to ignore when agent is speaking.
                If None, uses default list or reads from environment variable.
            interruption_words: List of words that should always interrupt.
                If None, uses default list or reads from environment variable.
        """
        # Load backchanneling words from environment or use defaults
        if backchanneling_words is None:
            env_words = os.getenv("LIVEKIT_BACKCHANNELING_WORDS")
            if env_words:
                backchanneling_words = [w.strip().lower() for w in env_words.split(",")]
            else:
                backchanneling_words = [
                    "yeah",
                    "ok",
                    "okay",
                    "oki",
                    "okey",
                    "kk",
                    "hmm",
                    "uh-huh",
                    "uh huh",
                    "right",
                    "sure",
                    "yep",
                    "yup",
                    "mhm",
                    "mm-hmm",
                    "mm hmm",
                    "aha",
                    "ah",
                    "i see",
                    "got it",
                    "alright",
                    "all right",
                    "uh",
                    "um",
                    "er",
                    "hm",
                ]

        # Load interruption words from environment or use defaults
        if interruption_words is None:
            env_words = os.getenv("LIVEKIT_INTERRUPTION_WORDS")
            if env_words:
                interruption_words = [w.strip().lower() for w in env_words.split(",")]
            else:
                interruption_words = [
                    "wait",
                    "stop",
                    "no",
                    "don't",
                    "dont",
                    "halt",
                    "pause",
                    "hold on",
                    "hold",
                    "cancel",
                    "nevermind",
                    "never mind",
                ]

        self._backchanneling_words = set(w.lower() for w in backchanneling_words)
        self._interruption_words = set(w.lower() for w in interruption_words)
        self._agent_speaking = False

        logger.info(
            "InterruptionHandler initialized",
            extra={
                "backchanneling_words_count": len(self._backchanneling_words),
                "interruption_words_count": len(self._interruption_words),
            },
        )

    def update_agent_state(self, state: str) -> None:
        """Update the agent's speaking state."""
        self._agent_speaking = state == "speaking"
        logger.debug(
            "InterruptionHandler: agent state updated",
            extra={"state": state, "agent_speaking": self._agent_speaking},
        )

    def is_backchanneling(self, transcript: str) -> bool:
        """Check if transcript contains only backchanneling words.

        Uses token-based detection to handle STT variations like "okay," or "okey".

        Args:
            transcript: The user's transcribed text

        Returns:
            True if transcript is only backchanneling, False otherwise
        """
        if not transcript or not transcript.strip():
            return False

        normalized = self._normalize_text(transcript)
        if not normalized:
            return False

        # Check if it contains interruption words - if so, not backchanneling
        if self._contains_interruption_word(normalized):
            return False

        # Token-based detection: split into words and check if all are backchanneling
        tokens = self._split_into_words(normalized)
        
        # Filter out empty tokens
        tokens = [t for t in tokens if t]
        
        # If no tokens, not backchanneling
        if not tokens:
            return False

        # Check if ALL tokens are backchanneling words
        # This handles cases like "okay okay" or "okay yeah" - all must be backchanneling
        all_backchanneling = all(token in self._backchanneling_words for token in tokens)
        
        if all_backchanneling:
            logger.debug(
                "Detected pure backchanneling",
                extra={"transcript": transcript, "normalized": normalized, "tokens": tokens},
            )
        
        return all_backchanneling

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        text = text.lower().strip()
        text = re.sub(r"[.,!?;:()\[\]{}'\"`]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_into_words(self, text: str) -> list[str]:
        """Split text into words, handling multi-word phrases and variations.
        
        This method handles STT variations by:
        1. Matching known phrases first (longest first)
        2. Then splitting remaining text into individual words
        3. Normalizing variations (e.g., "okey" -> "okay")
        """
        words = []
        remaining = text.lower()

        # First, try to match multi-word phrases (longest first)
        all_phrases = sorted(
            list(self._backchanneling_words) + list(self._interruption_words),
            key=len,
            reverse=True,
        )

        # Track which parts of the text we've matched
        matched_indices = []

        for phrase in all_phrases:
            # Use word boundaries to avoid partial matches
            pattern = r"\b" + re.escape(phrase) + r"\b"
            for match in re.finditer(pattern, remaining):
                start, end = match.span()
                # Check if this range overlaps with already matched text
                if not any(start < e and end > s for s, e in matched_indices):
                    matched_indices.append((start, end))
                    words.append(phrase)

        # Sort matched indices and extract unmatched parts
        matched_indices.sort()
        unmatched_parts = []
        last_end = 0
        
        for start, end in matched_indices:
            if start > last_end:
                unmatched_parts.append(remaining[last_end:start])
            last_end = end
        
        if last_end < len(remaining):
            unmatched_parts.append(remaining[last_end:])

        # Split unmatched parts into individual words
        for part in unmatched_parts:
            part_words = part.split()
            for word in part_words:
                word = word.strip()
                if word:
                    # Try to normalize common variations
                    normalized_word = self._normalize_variation(word)
                    words.append(normalized_word)

        return words

    def _normalize_variation(self, word: str) -> str:
        """Normalize common STT variations to standard forms.
        
        Examples:
            "okey" -> "okay"
            "oki" -> "ok"
            "kk" -> "ok"
        """
        # Map common variations to standard forms
        variation_map = {
            "okey": "okay",
            "oki": "ok",
            "kk": "ok",
            "k": "ok",  # Single "k" is often "ok"
        }
        
        word_lower = word.lower()
        return variation_map.get(word_lower, word_lower)

    def _contains_interruption_word(self, normalized_text: str) -> bool:
        """Check if text contains any interruption words."""
        for word in self._interruption_words:
            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, normalized_text):
                return True
        return False


class IntelligentInterruptionAgent(Agent):
    """Agent with intelligent interruption handling."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You would interact with users via voice. "
                "With that in mind keep your responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or other special characters in your responses. "
                "You are curious and friendly, and have a sense of humor. "
                "You will speak english to the user."
            )
        )
        self._interruption_handler = InterruptionHandler()
        self._pending_backchanneling_transcript: str | None = None
        self._was_interrupted_by_backchanneling = False

    async def on_enter(self):
        """Called when the agent enters the session."""
        session = self.session

        # Track agent state changes
        @session.on("agent_state_changed")
        def _on_agent_state_changed(ev: AgentStateChangedEvent):
            self._interruption_handler.update_agent_state(ev.new_state)

        # Handle user input transcription events (both interim and final)
        @session.on("user_input_transcribed")
        def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
            transcript = ev.transcript.strip()
            
            if not transcript:
                return

            # Only process if agent is speaking
            if not self._interruption_handler._agent_speaking:
                return

            # Token-based backchanneling check
            normalized = self._interruption_handler._normalize_text(transcript)
            if not normalized:
                return

            # Check for interruption words first - if found, allow interruption
            if self._interruption_handler._contains_interruption_word(normalized):
                logger.debug(
                    "Interruption word detected, allowing interruption",
                    extra={"transcript": transcript},
                )
                return

            # Split into tokens and check if all are backchanneling
            tokens = self._interruption_handler._split_into_words(normalized)
            tokens = [t for t in tokens if t]  # Filter empty tokens

            if not tokens:
                return

            # If all tokens are backchanneling words, ignore the interruption
            if all(token in self._interruption_handler._backchanneling_words for token in tokens):
                logger.info(
                    "Detected pure backchanneling while agent is speaking - ignoring interruption",
                    extra={
                        "transcript": transcript,
                        "normalized": normalized,
                        "tokens": tokens,
                        "is_final": ev.is_final,
                    },
                )
                self._pending_backchanneling_transcript = transcript
                self._was_interrupted_by_backchanneling = True

                # If this is a final transcript, try to clear the turn
                if ev.is_final:
                    try:
                        session.clear_user_turn()
                        logger.info("Cleared user turn for backchanneling input")
                    except Exception as e:
                        logger.warning(f"Could not clear user turn: {e}")

        # Handle false interruption events - resume immediately if it was backchanneling
        @session.on("agent_false_interruption")
        def _on_agent_false_interruption(ev: AgentFalseInterruptionEvent):
            if self._was_interrupted_by_backchanneling and self._pending_backchanneling_transcript:
                logger.info(
                    "Resuming from backchanneling interruption",
                    extra={"transcript": self._pending_backchanneling_transcript},
                )
                # The session will automatically resume if resume_false_interruption is True
                # We just need to clear our tracking
                self._pending_backchanneling_transcript = None
                self._was_interrupted_by_backchanneling = False

        # Generate initial reply
        self.session.generate_reply()

    async def on_user_turn_completed(self, turn_ctx, new_message):
        """Called when user finishes speaking."""
        transcript = new_message.content[0] if new_message.content else ""

        # If agent was speaking and this is just backchanneling, skip generating a reply
        if (
            self._was_interrupted_by_backchanneling
            and self._interruption_handler.is_backchanneling(transcript)
        ):
            logger.info(
                "Skipping reply generation for backchanneling input - raising StopResponse",
                extra={"transcript": transcript},
            )
            # Raise StopResponse to prevent generating a reply
            # The false interruption resume mechanism will handle continuing the previous speech
            self._pending_backchanneling_transcript = None
            self._was_interrupted_by_backchanneling = False
            raise StopResponse()

        # Reset tracking for normal input
        self._pending_backchanneling_transcript = None
        self._was_interrupted_by_backchanneling = False

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.

        Args:
            location: The location they are asking for
            latitude: The latitude of the location
            longitude: The longitude of the location
        """
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        # Enable false interruption resume - this is key for handling backchanneling
        resume_false_interruption=True,
        false_interruption_timeout=0.5,  # Short timeout for quick resume
    )

    # Log metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=IntelligentInterruptionAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)

