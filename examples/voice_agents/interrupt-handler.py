"""Enhanced Voice Agent with Robust Interruption Handling

This module implements a voice agent with sophisticated interruption handling capabilities,
including soft and hard interruption detection, state management, and comprehensive logging.
"""
from dataclasses import dataclass
import logging
import re
from typing import List, Dict, Set, Tuple 
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
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
    UserStateChangedEvent,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

load_dotenv()

# ----------------- WORD LISTS (from config) -----------------

from voice_agents.interrupt_config import SOFT_WORDS, HARD_WORDS

@dataclass
class InterruptionConfig:
    """Configuration for interruption handling."""
    soft_words: Set[str]
    hard_words: Set[str]
    min_interrupt_confidence: float = 0.7
    max_interrupt_duration: float = 2.0
    backchannel_timeout: float = 1.5


class InterruptionHandler:
    """Handles speech interruption logic with configurable word lists."""

    def __init__(self, config: InterruptionConfig):
        self.config = config
        self._last_interrupt_time = 0.0

    def get_tokens(self, text: str) -> List[str]:
        """Split text into lowercase tokens, removing non-alphabetic characters.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of lowercase word tokens
        """
        return [w for w in re.split(r"[^a-z]+", text.lower()) if w]

    def is_soft_interruption(self, words: List[str]) -> bool:
        """Check if the input consists solely of soft interruption words.
        
        Args:
            words: List of word tokens to check
            
        Returns:
            True if all words are soft interruption words, False otherwise
        """
        return bool(words) and all(w in self.config.soft_words for w in words)

    def has_hard_interruption(self, words: List[str]) -> bool:
        """Check if the input contains any hard interruption words.
        
        Args:
            words: List of word tokens to check
            
        Returns:
            True if any hard interruption words are found
        """
        return any(w in self.config.hard_words for w in words)

    def should_allow_interruption(self, words: List[str]) -> Tuple[bool, str]:
        """Determine if an interruption should be allowed based on input words.
        
        Args:
            words: List of word tokens to evaluate
            
        Returns:
            Tuple of (should_interrupt, reason) where reason explains the decision
        """
        current_time = time.time()
        time_since_last = current_time - self._last_interrupt_time
        
        # Rate limiting to prevent rapid successive interrupts
        if time_since_last < self.config.backchannel_timeout:
            return False, "rate_limited"
            
        if self.has_hard_interruption(words):
            self._last_interrupt_time = current_time
            return True, "hard_interrupt"
            
        if self.is_soft_interruption(words):
            self._last_interrupt_time = current_time
            return True, "soft_interrupt"
            
        return False, "no_match"


# ----------------- AGENT -----------------

class VoiceAgent(Agent):
    """Voice-enabled agent with enhanced interruption handling."""
    
    def __init__(self, interruption_config: InterruptionConfig) -> None:
        """Initialize the voice agent with interruption handling configuration.
        
        Args:
            interruption_config: Configuration for interruption handling
        """
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Keep responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or other special characters. "
                "You are curious and friendly, and have a sense of humor. "
                "You will speak English to the user."
            ),
        )
        self.interruption_handler = InterruptionHandler(interruption_config)
        self._logger = logging.getLogger("voice_agent")
        self._conversation_history: List[Dict[str, str]] = []

    async def on_enter(self):
        """Called when the agent first enters the conversation."""
        self._logger.info("Agent entering conversation")
        try:
            await self.session.generate_reply()
        except Exception as e:
            self._logger.error(f"Error generating initial reply: {e}", exc_info=True)
            raise

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ) -> str:
        """Get weather information for a specific location.
        
        Args:
            context: Current execution context
            location: Human-readable location name
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            String describing the weather conditions
        """
        self._logger.info(f"Looking up weather for {location} ({latitude}, {longitude})")
        # In a real implementation, this would call a weather API
        try:
            # Simulate API call
            await asyncio.sleep(0.5)
            return "The weather is sunny with a temperature of 70°F (21°C). Perfect weather for going outside!"
        except Exception as e:
            self._logger.error(f"Weather lookup failed: {e}", exc_info=True)
            return "I'm having trouble getting the weather information right now."


server = AgentServer()


def prewarm(proc: JobProcess):
    logger.info("[PREWARM] loading VAD model")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("[PREWARM] VAD model loaded")


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    logger.info("[ENTRYPOINT] starting AgentSession for room=%s", ctx.room.name)

    session = AgentSession(
        # REQUIRED MODELS
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="inworld/inworld-tts-1",

        # Turn detection + VAD
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],

        preemptive_generation=True,

        # false interruption handling (still useful)
        resume_false_interruption=True,
        false_interruption_timeout=1.0,

        # KEY SETTINGS:
        # DO NOT allow automatic interruptions of TTS by user speech.
        allow_interruptions=False,
        # BUT still keep user audio and send to STT while uninterruptible.
        discard_audio_if_uninterruptible=False,
    )

    # ------------- METRICS -------------

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"[METRICS] Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # ------------- DEBUG STATE LOGS -------------

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        logger.info(
            "[STATE] agent_state changed: %s -> %s | user_state=%s",
            ev.old_state,
            ev.new_state,
            session.user_state,
        )

    @session.on("user_state_changed")
    def _on_user_state_changed(ev: UserStateChangedEvent):
        logger.info(
            "[STATE] user_state changed: %s -> %s | agent_state=%s",
            ev.old_state,
            ev.new_state,
            session.agent_state,
        )

    # ------------- CORE STT LOGIC -------------

    @session.on("user_input_transcribed")
    async def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        """Handle transcribed user input with enhanced interruption logic."""
        try:
            text = (ev.transcript or "").strip()
            if not text:
                return

            # Only process final transcripts for now (partials can be noisy)
            if not ev.is_final:
                return

            # Get current state and handler
            agent = session.agent
            if not hasattr(agent, 'interruption_handler'):
                logger.warning("Agent does not have interruption_handler")
                return
                
            handler = agent.interruption_handler
            words = handler.get_tokens(text)
            
            logger.info(
                "[STT] %s | Text: %r | Agent State: %s | User State: %s",
                "FINAL" if ev.is_final else "PARTIAL",
                text,
                session.agent_state,
                session.user_state,
            )

            # Check if this should trigger an interruption
            should_interrupt, reason = handler.should_allow_interruption(words)
            
            logger.info(
                "[INTERRUPT] Words: %s | Should Interrupt: %s | Reason: %s | State: %s",
                words, should_interrupt, reason, session.agent_state
            )

            # Handle based on agent state
            if session.agent_state == "speaking":
                await _handle_agent_speaking(session, should_interrupt, reason, text)
            else:
                await _handle_agent_listening(session, words, text)
                
        except Exception as e:
            logger.error("Error in _on_user_input_transcribed: %s", e, exc_info=True)


async def _handle_agent_speaking(
    session: AgentSession, 
    should_interrupt: bool, 
    reason: str,
    text: str
) -> None:
    """Handle user input while agent is speaking."""
    logger.info(
        "[HANDLE_SPEAKING] Interrupt: %s | Reason: %s | Text: %r",
        should_interrupt, reason, text
    )
    
    if not should_interrupt:
        if reason == "rate_limited":
            logger.debug("Ignoring rapid successive input")
        return

    try:
        if reason == "hard_interrupt":
            logger.info("Processing hard interrupt")
            await session.interrupt(force=True)
        elif reason == "soft_interrupt":
            logger.debug("Processing soft interrupt")
            # For soft interrupts, we might want to be less aggressive
            await session.interrupt(force=False)
    except Exception as e:
        logger.error("Error during interrupt: %s", e, exc_info=True)


async def _handle_agent_listening(
    session: AgentSession,
    words: List[str],
    text: str
) -> None:
    """Handle user input while agent is listening."""
    logger.info(
        "[HANDLE_LISTENING] Text: %r | Words: %s",
        text, words
    )
    # No special handling needed when agent is listening
    # The framework will handle normal conversation flow

    # Initialize interruption configuration
    interruption_config = InterruptionConfig(
        soft_words=SOFT_WORDS,
        hard_words=HARD_WORDS,
        min_interrupt_confidence=0.7,
        max_interrupt_duration=2.0,
        backchannel_timeout=1.5
    )

    # Initialize and start the agent
    agent = VoiceAgent(interruption_config=interruption_config)
    
    try:
        await session.start(
            agent=agent,
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    # Enable noise cancellation if needed
                    # noise_cancellation=noise_cancellation.BVC(),
                ),
            ),
        )
    except Exception as e:
        logger.error("Failed to start agent session: %s", e, exc_info=True)
        raise


# if __name__ == "__main__":
#     logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s %(levelname)-5s %(name)-12s %(message)s",
#     )
#     cli.run_app(server)

if __name__ == "__main__":
    import os

    # Make sure proof/ exists
    os.makedirs("proof", exist_ok=True)

    # Console logging (optional, for debugging)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)-12s %(message)s",
    )

    # File logging for assignment proof
    file_handler = logging.FileHandler(
        "proof/log-transcript-demo.txt",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-5s %(name)-12s %(message)s")
    )

    # Attach to root logger so *all* logs (your [LOGIC], [STT], livekit.agents, etc.) go there
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    cli.run_app(server)