import asyncio
import logging
import os
import re
from typing import List, Set, Optional, Dict, Any

from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.agents.tokenize.basic import split_words
from livekit.plugins import cartesia, deepgram, openai, silero

# Setup logging and environment
load_dotenv()
logger = logging.getLogger(__name__)

# Regex to strip punctuation for word analysis
PUNCTUATION_REGEX = re.compile(r"[^\w\s-]")

class AgentSpeechManager:
    """
    Manages conversational flow by filtering interruptions based on user intent.
    
    Logic:
    1. 'Backchanneling' (e.g., "uh-huh", "yeah") is ignored if the agent is speaking.
    2. 'Stop commands' (e.g., "stop", "halt") force an immediate interruption.
    
    WARNING:
    This class relies on 'monkey-patching' (overriding) internal methods of the
    LiveKit `AgentSession` and `AgentActivity`. These are private APIs (`_methods`)
    and may break in future library updates.
    """

    # Default patterns to ignore if the user provides no specific config
    DEFAULT_IGNORE_PATTERNS = [
        r"yeah?", r"ok(ay)?", r"h+m+", r"right", r"uh-?huh", r"aha", r"yep",
        r"uh+", r"um+", r"mm-?hmm+", r"yes", r"sure", "got it", r"alright",
        r"mhm+", r"yup", r"correct", r"gotcha", r"roger", r"indeed",
        r"exactly", r"absolutely", r"understood", r"see", r"true",
        r"agreed", r"fine", "good", "nice", "great", "wow", "oh",
    ]

    # Default words that trigger an immediate halt
    DEFAULT_STOP_WORDS = {"stop", "wait", "no", "halt", "pause", "cancel"}

    def __init__(
        self,
        ignorable_phrases: Optional[List[str]] = None,
        stop_phrases: Optional[List[str]] = None,
    ):
        # compile regex for ignorable phrases (backchannels)
        patterns = ignorable_phrases if ignorable_phrases else self.DEFAULT_IGNORE_PATTERNS
        self.ignorable_phrase_patterns = [
            re.compile(p, re.IGNORECASE) for p in patterns
        ]

        # Set up stop words (commands that override everything)
        self.stop_phrases: Set[str] = (
            {w.lower() for w in stop_phrases}
            if stop_phrases
            else self.DEFAULT_STOP_WORDS
        )

        # State management
        self._session: Optional[AgentSession] = None
        self._activity: Any = None  # Reference to the internal activity monitor
        self._agent_state = "idle"
        self._word_cache: Dict[str, List[str]] = {} # Cache to avoid re-tokenizing same strings
        self._original_methods: Dict[str, Any] = {} # Store original methods before patching

    def attach(self, session: AgentSession) -> None:
        """
        Connects the manager to a specific agent session and begins the patching process.
        """
        self._session = session
        # Listen for state changes (speaking vs listening)
        session.on("agent_state_changed", self._monitor_state)
        # Start the patching process asynchronously (must wait for activity to initialize)
        asyncio.create_task(self._patch_internals())

    async def _patch_internals(self) -> None:
        """
        Waits for the session's internal `_activity` object to exist, then overrides
        its methods to inject our custom interruption logic.
        """
        try:
            self._activity = await self._wait_for_activity_initialization()
        except asyncio.TimeoutError:
            logger.error("Timeout: AgentActivity never initialized. Interruption filter is disabled.")
            return

        # --- Monkey Patching Internal Methods ---
        # 1. Handle raw audio energy (VAD)
        self._override_method("_interrupt_by_audio_activity", self._handle_audio_interruption)
        # 2. Handle completed sentences
        self._override_method("on_final_transcript", self._handle_final_transcript)
        # 3. Handle processing sentences (partial results)
        self._override_method("on_interim_transcript", self._handle_interim_transcript)
        # 4. Handle end-of-turn logic
        self._override_method("on_end_of_turn", self._handle_turn_completion)

        if self._original_methods:
            logger.info("AgentSpeechManager: Successfully injected custom interruption logic.")
        else:
            logger.error("AgentSpeechManager: Failed to inject logic.")

    async def _wait_for_activity_initialization(self, timeout: float = 5.0):
        """Polls for the existence of `_activity` on the session."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if getattr(self._session, "_activity", None) is not None:
                return self._session._activity
            await asyncio.sleep(0.05)
        raise asyncio.TimeoutError()

    def _override_method(self, method_name: str, new_handler) -> None:
        """Safely swaps a method on `self._activity` with a new one, saving the old one."""
        if hasattr(self._activity, method_name):
            original = getattr(self._activity, method_name)
            self._original_methods[method_name] = original
            setattr(self._activity, method_name, new_handler)
        else:
            logger.warning(f"Patching failed: Attribute '{method_name}' not found on activity.")

    def _monitor_state(self, state_event) -> None:
        """Callback to track if the agent thinks it is speaking or listening."""
        self._agent_state = state_event.new_state

    # --- Helper Logic ---

    def _tokenize_transcript(self, transcript: str) -> List[str]:
        """
        Cleans and splits a transcript into a list of words.
        Uses a cache to prevent redundant processing of the same strings.
        """
        # Remove punctuation
        clean_text = PUNCTUATION_REGEX.sub(" ", transcript)
        
        # Check cache
        if transcript in self._word_cache:
            return self._word_cache[transcript]

        # Tokenize using LiveKit's utility
        word_tuples = split_words(clean_text, split_character=True)
        words = [w[0].lower().strip() for w in word_tuples if w[0].strip()]

        # Basic cache eviction (LRU-ish)
        if len(self._word_cache) > 100:
            self._word_cache.pop(next(iter(self._word_cache)))
        
        self._word_cache[transcript] = words
        return words

    def _is_pure_backchannel(self, words: List[str]) -> bool:
        """Returns True if the input consists ONLY of ignorable affirmation words."""
        if not words:
            return False
        return all(self._matches_ignore_pattern(word) for word in words)

    def _matches_ignore_pattern(self, word: str) -> bool:
        """Checks a single word against the regex list."""
        for pattern in self.ignorable_phrase_patterns:
            if pattern.fullmatch(word):
                return True
        return False

    @property
    def _is_agent_speaking(self) -> bool:
        """
        Determines if the agent is actively outputting audio.
        Checks both the high-level state and the internal audio buffer.
        """
        if self._activity is None:
            return False

        is_in_speaking_state = self._agent_state == "speaking"
        
        # Deep check: is there actual audio data queued that hasn't been interrupted?
        has_active_speech_handle = (
            hasattr(self._activity, '_current_speech') and
            self._activity._current_speech is not None and
            not self._activity._current_speech.interrupted
        )
        return is_in_speaking_state or has_active_speech_handle

    def _execute_hard_stop(self) -> None:
        """
        Forcefully kills current speech synthesis and clears the user's turn queue.
        Used when a 'stop word' is detected.
        """
        if self._activity is None:
            return

        # 1. Interrupt current audio playback
        if hasattr(self._activity, '_current_speech') and self._activity._current_speech:
            self._activity._current_speech.interrupt(force=True)

        # 2. Cancel any preemptive generation (streaming text that hasn't been spoken yet)
        if hasattr(self._activity, '_preemptive_generation') and self._activity._preemptive_generation:
            gen = self._activity._preemptive_generation
            if hasattr(gen, 'speech_handle') and hasattr(gen.speech_handle, '_cancel'):
                gen.speech_handle._cancel()
            self._activity._preemptive_generation = None

        # 3. Clear the logic queue so the agent doesn't reply to the "Stop"
        if self._session:
            self._session.clear_user_turn()

        self._reset_stt_buffer()

    def _reset_stt_buffer(self) -> None:
        """Manually clears the internal Speech-to-Text buffers."""
        if self._activity and hasattr(self._activity, '_audio_recognition'):
            ar = self._activity._audio_recognition
            if ar:
                ar._audio_transcript = ""
                ar._audio_interim_transcript = ""

    # --- The Overridden Event Handlers ---

    def _handle_audio_interruption(self) -> None:
        """
        Called when VAD detects noise/voice.
        Logic: If agent is speaking and the user just says "mhmm", ignore it.
        """
        transcript = ""
        if self._activity and hasattr(self._activity, '_audio_recognition'):
            if self._activity._audio_recognition:
                transcript = self._activity._audio_recognition.current_transcript or ""

        words = self._tokenize_transcript(transcript)

        # Guard: If agent is speaking and it's empty or just backchannel -> Don't interrupt
        if self._is_agent_speaking:
            if not transcript.strip():
                return
            if self._is_pure_backchannel(words):
                return

        # Otherwise, call the original method (which triggers the interruption)
        original = self._original_methods.get("_interrupt_by_audio_activity")
        if original:
            original()

    def _handle_final_transcript(self, transcript_event, *, speaking=None) -> None:
        """
        Called when STT finalizes a sentence.
        Logic: Check for stop words, then backchanneling.
        """
        original = self._original_methods.get("on_final_transcript")
        
        # Safety check for empty transcripts
        if not (transcript_event.alternatives and transcript_event.alternatives[0].text):
            if original: original(transcript_event, speaking=speaking)
            return

        transcript = transcript_event.alternatives[0].text.strip()
        words = self._tokenize_transcript(transcript)

        if not words:
            if original: original(transcript_event, speaking=speaking)
            return

        # Case A: User said a Hard Stop word -> Kill everything
        if any(word in self.stop_phrases for word in words):
            self._execute_hard_stop()
            if original: original(transcript_event, speaking=speaking)
            return

        # Case B: User is just backchanneling while Agent speaks -> Ignore and clear buffer
        elif self._is_agent_speaking and self._is_pure_backchannel(words):
            self._reset_stt_buffer()
            return

        # Case C: Valid input -> Process normally
        if original:
            original(transcript_event, speaking=speaking)

    def _handle_interim_transcript(self, transcript_event, *, speaking=None) -> None:
        """
        Called when STT has partial results.
        Allows for faster reaction to "Stop" commands before the sentence ends.
        """
        original = self._original_methods.get("on_interim_transcript")
        
        if transcript_event.alternatives and transcript_event.alternatives[0].text:
            transcript = transcript_event.alternatives[0].text.strip()
            words = self._tokenize_transcript(transcript)

            if words:
                # Immediate check for stop words
                if any(word in self.stop_phrases for word in words):
                    self._execute_hard_stop()
                    if original: original(transcript_event, speaking=speaking)
                    return
                
                # Immediate check for backchannel to suppress interim interruptions
                elif self._is_agent_speaking and self._is_pure_backchannel(words):
                    if self._activity and hasattr(self._activity, '_audio_recognition'):
                        # Clear interim buffer so it doesn't build up
                        if self._activity._audio_recognition:
                            self._activity._audio_recognition._audio_interim_transcript = ""
                    return

        if original:
            original(transcript_event, speaking=speaking)

    def _handle_turn_completion(self, turn_info) -> bool:
        """
        Called when the system decides the user is done talking.
        Returns True if the turn should proceed, False if it should be ignored.
        """
        original = self._original_methods.get("on_end_of_turn", lambda _: True)

        if not turn_info.new_transcript:
            return original(turn_info)

        words = self._tokenize_transcript(turn_info.new_transcript.strip())
        if not words:
            return original(turn_info)

        # If it was a stop command, we already handled it, so return False to cancel normal processing
        if any(word in self.stop_phrases for word in words):
            self._execute_hard_stop()
            return False

        # If it was just backchanneling, return False so the Agent doesn't reply "I heard you say yes"
        if self._is_agent_speaking and self._is_pure_backchannel(words):
            return False

        return original(turn_info)


# --- Main Application Setup ---

server = AgentServer()

@server.rtc_session()
async def session_entrypoint(job: JobContext):
    """
    Entrypoint for the Agent.
    Initializes plugins and attaches the Speech Manager logic.
    """
    session = AgentSession(
        vad=silero.VAD.load(),
        llm="openai/gpt-4.1-mini",
        stt="deepgram/nova-3",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        false_interruption_timeout=None, # We are handling interruptions manually
        min_interruption_words=1,
    )

    # Load configuration
    ignore_words_str = os.getenv("LIVEKIT_IGNORE_WORDS")
    interrupt_words_str = os.getenv("LIVEKIT_INTERRUPT_WORDS")

    ignorable_phrases = ignore_words_str.split(',') if ignore_words_str else None
    stop_phrases = interrupt_words_str.split(',') if interrupt_words_str else None

    # Attach the manager
    speech_manager = AgentSpeechManager(
        ignorable_phrases=ignorable_phrases,
        stop_phrases=stop_phrases,
    )
    speech_manager.attach(session)

    # Start the agent
    await session.start(
        agent=Agent(
            instructions=(
                "You are a helpful assistant. When explaining something, "
                "speak clearly and continue your explanation even if the user "
                "says brief acknowledgements like 'yeah' or 'ok'. Only stop if "
                "they explicitly say 'stop', 'wait', or 'no'."
            )
        ),
        room=job.room,
    )

if __name__ == "__main__":
    cli.run_app(server)