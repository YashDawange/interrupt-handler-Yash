import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentFalseInterruptionEvent,
    AgentServer,
    AgentSession,
    AgentStateChangedEvent,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    UserInputTranscribedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import cartesia, deepgram, groq, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

# Load .env file from project root (parent of examples directory)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


class BackchannelFilter:
    """Prevents interruptions from backchanneling words (filler words like 'yeah', 'ok', etc.)
    when the agent is currently speaking. The agent will continue speaking seamlessly without
    pausing or stuttering when it detects passive acknowledgements."""

    # Default backchanneling words and phrases (can be overridden via BACKCHANNEL_WORDS env var)
    DEFAULT_BACKCHANNEL_PATTERNS = [
        r"^(yeah|yes|yep|yup)$",
        r"^(ok|okay|k)$",
        r"^(aha|ah|uh|um)$",
        r"^(hmm|mm|mhm)$",
        r"^(right|sure|got it|gotcha)$",
        r"^(alright|alrighty)$",
        r"^(uh huh|uh-huh)$",
    ]

    @classmethod
    def _load_patterns(cls) -> list[str]:
        """Load backchannel patterns from environment variable or use defaults.
        
        Environment variable format: BACKCHANNEL_WORDS=yeah,ok,aha,hmm,right,alright,uh-huh
        Each word/phrase will be wrapped in a regex pattern: ^(word)$
        For multi-word phrases, include them as-is: uh-huh, got it
        """
        env_words = os.getenv("BACKCHANNEL_WORDS", "").strip()
        if env_words:
            # Parse comma-separated list from environment variable
            words = [w.strip() for w in env_words.split(",") if w.strip()]
            if words:
                logger.info(f"Loaded {len(words)} backchannel words from BACKCHANNEL_WORDS env var")
                # Create regex patterns for each word/phrase
                return [rf"^{re.escape(word)}$" for word in words]
        
        # Use default patterns
        logger.debug("Using default backchannel patterns")
        return cls.DEFAULT_BACKCHANNEL_PATTERNS

    def __init__(self, session: AgentSession, patterns: list[str] | None = None):
        """Initialize the backchannel filter.
        
        Args:
            session: The AgentSession to monitor
            patterns: Optional list of regex patterns for backchannel detection.
                     If None, patterns are loaded from BACKCHANNEL_WORDS env var or defaults.
        """
        self._session = session
        self._agent_is_speaking = False
        
        # Load patterns (from parameter, env var, or defaults)
        if patterns is None:
            patterns = self._load_patterns()
        
        self._patterns = patterns
        self._backchannel_pattern = re.compile(
            "|".join(patterns), re.IGNORECASE
        )
        self._pending_backchannel = False

    def _is_backchannel(self, text: str) -> bool:
        """Check if the transcribed text is a backchannel word."""
        # Normalize text: strip whitespace and punctuation
        normalized = text.strip().strip(".,!?;:").lower()
        # Check if it matches any backchannel pattern
        return bool(self._backchannel_pattern.match(normalized))

    def _on_agent_state_changed(self, ev: AgentStateChangedEvent) -> None:
        """Track agent speaking state."""
        was_speaking = self._agent_is_speaking
        self._agent_is_speaking = ev.new_state == "speaking"
        logger.debug(
            f"BackchannelFilter: agent state changed {ev.old_state} -> {ev.new_state} "
            f"(is_speaking={self._agent_is_speaking})"
        )
        
        if ev.new_state == "speaking" and not was_speaking:
            # Agent just started speaking, clear any pending backchannel flag
            self._pending_backchannel = False

    def _on_user_input_transcribed(self, ev: UserInputTranscribedEvent) -> None:
        """Handle user transcription events to detect and filter backchanneling.
        
        Logic Matrix:
        - Agent Speaking + Backchannel ("Yeah/Ok/Hmm") → IGNORE: Continue speaking seamlessly
        - Agent Speaking + Real Input ("Wait/Stop/No") → INTERRUPT: Stop and listen
        - Agent Silent + Backchannel ("Yeah/Ok/Hmm") → RESPOND: Treat as valid input
        - Agent Silent + Real Input ("Start/Hello") → RESPOND: Normal behavior
        """
        # Process both interim and final transcripts for faster response
        logger.debug(
            f"BackchannelFilter: received transcript '{ev.transcript}' "
            f"(is_final={ev.is_final}, agent_speaking={self._agent_is_speaking})"
        )

        # Only filter backchannels when agent is speaking
        # When agent is silent, backchannels should be processed as valid input
        if not self._agent_is_speaking:
            logger.debug(
                f"BackchannelFilter: agent not speaking - allowing normal processing "
                f"(backchannels will be treated as valid input)"
            )
            return

        # Agent is speaking - check if this is a backchannel
        # For interim transcripts, check the first word immediately for faster response
        transcript_lower = ev.transcript.lower().strip()
        
        # First check the full transcript for phrases like "uh-huh" that might be split
        full_text_is_backchannel = self._is_backchannel(ev.transcript)
        
        if not full_text_is_backchannel:
            # Check if ALL words in the transcript are backchannels
            # Split by common separators but keep the original for full phrase matching
            transcript_words = re.split(r'[\s,\.]+', transcript_lower)
            transcript_words = [w for w in transcript_words if w]  # Remove empty strings
            
            # For interim transcripts, check the first word immediately
            # This allows us to resume audio faster
            if not ev.is_final and transcript_words:
                first_word = transcript_words[0]
                if self._is_backchannel(first_word):
                    # Likely a backchannel - resume immediately while waiting for more words
                    logger.debug(
                        f"Interim transcript first word '{first_word}' is backchannel - "
                        "resuming audio preemptively"
                    )
                    self._resume_audio_immediately()
                    # Don't clear user turn yet - wait to confirm it's all backchannels
            
            # Check if ALL words are backchannels (for cases like "okay yeah" or "yeah okay")
            all_backchannels = all(self._is_backchannel(word) for word in transcript_words if word)
            
            if not all_backchannels:
                # Contains meaningful words - allow interruption (e.g., "Wait/Stop/No")
                if self._pending_backchannel:
                    logger.debug(
                        f"Real user input detected after backchannel: '{ev.transcript}' "
                        "- allowing interruption"
                    )
                self._pending_backchannel = False
                return
        
        # If we reach here, the transcript is a backchannel AND agent is speaking
        # IGNORE: Clear user turn and resume audio to continue speaking seamlessly
        self._pending_backchannel = True
        logger.info(
            f"Backchannel detected (agent speaking): '{ev.transcript}' "
            f"(is_final={ev.is_final}) - ignoring and continuing to speak"
        )

        # CRITICAL: Resume audio FIRST (before clearing) to minimize any pause
        # This ensures seamless continuation of speech
        self._resume_audio_immediately()

        # CRITICAL: Clear the user turn IMMEDIATELY to prevent the transcript from being processed
        # This prevents the agent from generating a reply to the backchannel
        # We do this for both interim and final transcripts
        try:
            # Clear the user input buffer to prevent the agent from processing this transcript
            self._session.clear_user_turn()
            logger.info(
                f"Cleared user turn for backchannel: '{ev.transcript}' "
                f"(is_final={ev.is_final}) - agent will continue speaking"
            )
        except Exception as e:
            logger.warning(f"Failed to clear user turn: {e}")
    
    def _resume_audio_immediately(self) -> None:
        """Immediately resume audio output to prevent any pause or stutter.
        
        This method aggressively resumes audio and updates agent state to ensure
        seamless continuation when a backchannel is detected.
        """
        if not self._session.options.resume_false_interruption:
            return
        
        audio_output = self._session.output.audio
        if not audio_output or not audio_output.can_pause:
            return
        
        try:
            # Update agent state to "speaking" BEFORE resuming audio
            # This ensures the system knows the agent should continue speaking
            if self._session.agent_state != "speaking":
                # Use internal method to update state directly (matches false interruption handler)
                self._session._update_agent_state("speaking")
                logger.debug("Updated agent state to 'speaking' before resuming audio")
            
            # Resume audio output immediately - this will continue the agent's speech
            # seamlessly without any pause or stutter
            audio_output.resume()
            logger.debug("Immediately resumed agent speech after backchannel detection")
        except AttributeError:
            # _update_agent_state might not be accessible, try without it
            try:
                audio_output.resume()
                logger.debug("Resumed audio (state update not available)")
            except Exception as e:
                logger.debug(f"Audio resume attempted (may already be playing): {e}")
        except Exception as e:
            logger.debug(f"Audio resume attempted (may already be playing): {e}")
    
    def _on_false_interruption(self, ev: AgentFalseInterruptionEvent) -> None:
        """Handle false interruption events - if we have a pending backchannel, ensure audio resumes."""
        if self._pending_backchannel and not ev.resumed:
            # System detected a false interruption, and we know it's a backchannel
            # Ensure audio is resumed if it wasn't already
            logger.debug("False interruption detected for backchannel, ensuring audio resumes")
            self._resume_audio_immediately()

    async def start(self) -> None:
        """Start listening to session events."""
        self._session.on("agent_state_changed", self._on_agent_state_changed)
        self._session.on("user_input_transcribed", self._on_user_input_transcribed)
        # Initialize state
        self._agent_is_speaking = self._session.agent_state == "speaking"


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice."
            "with that in mind keep your responses concise and to the point."
            "do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "you will speak english to the user",
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        Ensure the user's location (city or region) is provided.
        When given a location, please estimate the latitude and longitude of the location and
        do not ask the user for them.

        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # Using Groq for fast inference (free tier available). See all available models at https://docs.livekit.io/agents/models/llm/
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=cartesia.TTS(voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
        # when it's detected, you may resume the agent's speech
        # Use a very short timeout so we can quickly resume on backchannel detection
        resume_false_interruption=True,
        false_interruption_timeout=0.02,  # Extremely short timeout (20ms) for immediate resume on backchannel
        # Require at least 1 word to be transcribed before interrupting - this gives us time to detect backchannel words
        # and prevents pause until we know what the user said
        min_interruption_words=1,
        # Minimum duration before interruption is registered - very small buffer to allow transcription
        # but large enough to allow VAD to trigger pause before STT confirms it's a backchannel
        min_interruption_duration=0.05,  # Reduced to 50ms for faster backchannel detection
    )

    # Initialize backchannel filter to prevent interruptions from filler words
    # Register event listeners BEFORE starting the session to ensure we catch all events
    backchannel_filter = BackchannelFilter(session)
    session.on("agent_state_changed", backchannel_filter._on_agent_state_changed)
    session.on("user_input_transcribed", backchannel_filter._on_user_input_transcribed)
    session.on("agent_false_interruption", backchannel_filter._on_false_interruption)
    logger.info("Backchannel filter initialized and event listeners registered")

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # uncomment to enable the Krisp BVC noise cancellation
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
