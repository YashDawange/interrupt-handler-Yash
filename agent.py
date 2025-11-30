import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set
from datetime import datetime

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.agents.tokenize.basic import split_words
from livekit.plugins import cartesia, deepgram, google, silero

logger = logging.getLogger("contextual-speech-manager")
logger.setLevel(logging.DEBUG)

load_dotenv(".env.local")

_PUNCTUATION_PATTERN = re.compile(r'[^\w\s]')
_MULTI_SPACE_PATTERN = re.compile(r'\s+')


class ConversationState(Enum):
    """
    Enum representing the current state of the AI agent in the conversation flow.

    States:
        IDLE: Agent is not actively processing or producing output
        LISTENING: Agent is actively receiving user input
        PROCESSING: Agent is generating a response internally
        SPEAKING: Agent is actively producing audio output
        INTERRUPTED: Agent was interrupted by user input
    """
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"


@dataclass
class FilterConfiguration:
    """
    Configuration for the contextual speech filter.

    Attributes:
        backchannel_tokens: Set of words to ignore when agent is speaking
        interruption_triggers: Set of words that always cause interruption
        validation_window_ms: Time window (ms) to wait for complete transcription
        min_token_length: Minimum length for a token to be considered
    """
    backchannel_tokens: Set[str] = field(default_factory=set)
    interruption_triggers: Set[str] = field(default_factory=set)
    validation_window_ms: float = 300.0
    min_token_length: int = 1

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.validation_window_ms <= 0:
            raise ValueError("validation_window_ms must be positive")
        if self.min_token_length < 1:
            raise ValueError("min_token_length must be at least 1")

        # If no words were provided, use our default list of common "yeah, ok" type words
        if not self.backchannel_tokens:
            self.backchannel_tokens = {
                "yeah", "ok", "hmm", "right", "uh-huh", "aha", "yep", "okay",
                "uh", "um", "mm-hmm", "yes", "sure", "alright", "mhm", "yup",
                "correct", "gotcha", "roger", "indeed", "exactly", "absolutely",
                "understood", "see", "true", "agreed", "fine", "good", "nice",
                "great", "wow", "oh", "i", "know", "get", "it"
            }

        if not self.interruption_triggers:
            self.interruption_triggers = {
                "stop", "wait", "no", "halt", "pause", "cancel", "hold"
            }


class ContextualSpeechFilter:
    """
    Speech filter that distinguishes between passive acknowledgments 
    (backchanneling) and active interruptions based on conversation context.

    Intercepts and validates interruption events before they disrupt agent speech,
    solving the VAD-STT timing gap by queuing interrupts and validating them
    asynchronously once transcription is available.
    """

    def __init__(
        self,
        backchannel_words: List[str] | None = None,
        interruption_commands: List[str] | None = None,
        validation_timeout: float = 0.3,
        min_word_length: int = 1,
    ):
        """
        Initialize the contextual speech filter.

        Args:
            backchannel_words: List of passive acknowledgment words to filter when 
                              agent is speaking. If None, uses comprehensive default set.
            interruption_commands: List of words that should always trigger interruption.
                                  If None, uses default command set.
            validation_timeout: Maximum time (seconds) to wait for STT transcription 
                               before making an interruption decision. Default: 0.3s
            min_word_length: Minimum character length for a word to be considered 
                            in filtering logic. Default: 1
        """
        self.config = FilterConfiguration(
            backchannel_tokens=set(
                w.lower() for w in backchannel_words) if backchannel_words else set(),
            interruption_triggers=set(
                w.lower() for w in interruption_commands) if interruption_commands else set(),
            validation_window_ms=validation_timeout * 1000,
            min_token_length=min_word_length,
        )

        self._original_methods = {
            'interrupt': None,
            'final_transcript': None,
            'interim_transcript': None,
            'end_of_turn': None,
        }

        self._conversation_state = ConversationState.IDLE

        self._session_ref = None
        self._activity_ref = None
        self._audio_recognition_ref = None

        # Queue to hold interrupts while we wait for speech-to-text to catch up
        # This solves the timing problem where voice detection happens before transcription
        self._interrupt_queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._validation_worker: asyncio.Task | None = None

        logger.info(
            f"ContextualSpeechFilter initialized:\n"
            f"  Backchannel tokens: {len(self.config.backchannel_tokens)}\n"
            f"  Interruption triggers: {len(self.config.interruption_triggers)}\n"
            f"  Validation window: {validation_timeout}s"
        )

    async def _validation_worker_loop(self) -> None:
        """
        Async worker that processes queued interrupts and validates them against
        speech-to-text transcription with configurable timeout.

        Solves the VAD-STT timing gap by queuing interrupts and validating them
        once transcription is available.
        """
        logger.info("Validation worker loop initiated")

        try:
            while True:
                try:
                    # Wait for an interrupt to show up in the queue
                    interrupt_event = await asyncio.wait_for(
                        self._interrupt_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                activity_ref, event_timestamp = interrupt_event
                validation_start = datetime.now()

                try:
                    transcript_text = await self._await_transcription(
                        activity_ref,
                        timeout_seconds=self.config.validation_window_ms / 1000
                    )

                    should_allow_interrupt = self._evaluate_interruption(
                        activity_ref,
                        transcript_text
                    )

                    validation_duration = (
                        datetime.now() - validation_start).total_seconds()

                    logger.debug(
                        f"Validation complete: transcript='{transcript_text}', "
                        f"allow={should_allow_interrupt}, "
                        f"state={self._conversation_state.value}, "
                        f"duration={validation_duration*1000:.1f}ms"
                    )

                    if should_allow_interrupt:
                        if self._original_methods['interrupt']:
                            self._original_methods['interrupt']()
                    else:
                        logger.debug(
                            f"Filtered backchannel utterance: '{transcript_text}'")

                except Exception as e:
                    logger.error(
                        f"Error during interrupt validation: {e}", exc_info=True)
                    if self._original_methods['interrupt']:
                        self._original_methods['interrupt']()

        except asyncio.CancelledError:
            logger.info("Validation worker loop terminated")
        except Exception as e:
            logger.error(
                f"Fatal error in validation worker loop: {e}", exc_info=True)

    async def _await_transcription(
        self,
        activity_ref,
        timeout_seconds: float
    ) -> str:
        """
        Wait for STT transcription to become available within timeout window.

        Args:
            activity_ref: Reference to AgentActivity instance
            timeout_seconds: Maximum time to wait for transcription

        Returns:
            Current transcript text, or empty string if timeout
        """
        start_time = datetime.now()
        last_transcript = ""
        poll_interval = 0.01

        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            audio_recognition = self._audio_recognition_ref or activity_ref._audio_recognition
            if audio_recognition is not None:
                current_transcript = audio_recognition.current_transcript or ""
                if current_transcript and current_transcript != last_transcript:
                    last_transcript = current_transcript
                    return current_transcript
            await asyncio.sleep(poll_interval)

        return last_transcript

    def install(self, session: AgentSession) -> None:
        """
        Install the contextual speech filter into the LiveKit agent session.

        This method performs dynamic interception of LiveKit's internal methods
        to inject our filtering logic at critical points in the audio processing
        pipeline:
        1. VAD audio activity detection
        2. Interim transcript updates
        3. Final transcript completion
        4. Turn ending logic

        Args:
            session: The AgentSession instance to instrument
        """
        self._session_ref = session

        session.on("agent_state_changed", self._track_state_change)
        session.on("user_input_transcribed", self._track_user_transcript)

        self._validation_worker = asyncio.create_task(
            self._validation_worker_loop())
        logger.debug("Validation worker task spawned")

        async def _deferred_installation():
            """
            Wait for AgentActivity to be initialized, then install interceptors.
            AgentActivity is not immediately available at session creation time.
            """
            max_wait_duration = 2.0
            poll_interval = 0.05
            elapsed_time = 0.0

            while elapsed_time < max_wait_duration:
                if session._activity is not None:
                    break
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval

            if session._activity is None:
                logger.error(
                    "AgentActivity initialization timeout - filter not installed!")
                return

            activity = session._activity
            self._activity_ref = activity
            self._audio_recognition_ref = activity._audio_recognition

            self._original_methods['interrupt'] = activity._interrupt_by_audio_activity
            self._original_methods['final_transcript'] = activity.on_final_transcript
            self._original_methods['interim_transcript'] = activity.on_interim_transcript
            self._original_methods['end_of_turn'] = activity.on_end_of_turn

            def _wrap_audio_interrupt():
                return self._intercept_vad_interrupt(activity)

            def _wrap_final_transcript(ev, *, speaking=None):
                return self._intercept_final_transcript(activity, ev, speaking=speaking)

            def _wrap_interim_transcript(ev, *, speaking=None):
                return self._intercept_interim_transcript(activity, ev, speaking=speaking)

            def _wrap_turn_ending(info):
                return self._intercept_turn_ending(activity, info)

            activity._interrupt_by_audio_activity = _wrap_audio_interrupt
            activity.on_final_transcript = _wrap_final_transcript
            activity.on_interim_transcript = _wrap_interim_transcript
            activity.on_end_of_turn = _wrap_turn_ending

            logger.info("ContextualSpeechFilter successfully installed")

        asyncio.create_task(_deferred_installation())

    def _track_state_change(self, ev) -> None:
        """
        Track conversation state transitions.

        Maps LiveKit agent state events to our internal ConversationState enum.

        Args:
            ev: State change event from LiveKit
        """
        try:
            previous_state = self._conversation_state

            state_string = ev.new_state.lower() if hasattr(ev, 'new_state') else 'idle'

            state_mapping = {
                "speaking": ConversationState.SPEAKING,
                "listening": ConversationState.LISTENING,
                "thinking": ConversationState.PROCESSING,
                "processing": ConversationState.PROCESSING,
                "interrupted": ConversationState.INTERRUPTED,
                "idle": ConversationState.IDLE,
            }

            self._conversation_state = state_mapping.get(
                state_string,
                ConversationState.IDLE
            )

            if previous_state != self._conversation_state:
                logger.debug(
                    f"State transition: {previous_state.value} → {self._conversation_state.value}"
                )
        except Exception as e:
            logger.error(f"Error tracking state change: {e}", exc_info=True)

    def _track_user_transcript(self, ev) -> None:
        """
        Track user transcript updates for debugging.

        Args:
            ev: Transcript event from LiveKit
        """
        try:
            if hasattr(ev, 'transcript') and ev.transcript:
                logger.debug(
                    f"User transcript: '{ev.transcript[:50]}{'...' if len(ev.transcript) > 50 else ''}'"
                )
        except Exception as e:
            logger.error(f"Error tracking user transcript: {e}", exc_info=True)

    def _execute_immediate_interruption(self, activity) -> None:
        """
        Execute immediate interruption of agent speech and clear all related state.

        This is the nuclear option - it forcefully stops all speech generation,
        cancels pending audio, and resets transcription state. Used when explicit
        interruption commands are detected.

        Args:
            activity: The AgentActivity instance
        """
        try:
            logger.debug("Executing immediate interruption sequence")

            if activity._current_speech:
                try:
                    activity._current_speech.interrupt(force=True)
                    logger.debug("Terminated active speech stream")
                except Exception as e:
                    logger.error(f"Failed to interrupt speech: {e}")

            if hasattr(activity, '_preemptive_generation') and activity._preemptive_generation:
                try:
                    activity._preemptive_generation.speech_handle._cancel()
                    activity._preemptive_generation = None
                    logger.debug("Cancelled preemptive generation pipeline")
                except Exception as e:
                    logger.error(
                        f"Failed to cancel preemptive generation: {e}")

            if self._session_ref:
                try:
                    self._session_ref.clear_user_turn()
                    logger.debug("Cleared user turn context")
                except Exception as e:
                    logger.error(f"Failed to clear user turn: {e}")

            audio_recognition = self._audio_recognition_ref or activity._audio_recognition
            if audio_recognition is not None:
                try:
                    audio_recognition._audio_transcript = ""
                    audio_recognition._audio_interim_transcript = ""
                    logger.debug("Reset audio transcription buffers")
                except Exception as e:
                    logger.error(f"Failed to clear transcripts: {e}")

        except Exception as e:
            logger.error(
                f"Error in immediate interruption sequence: {e}", exc_info=True)

    def _is_agent_currently_speaking(self, activity) -> bool:
        """
        Determine if the agent is actively producing speech output.

        Uses multiple indicators for robust detection:
        1. Explicit conversation state
        2. Active speech object existence
        3. Speech interruption status

        Args:
            activity: The AgentActivity instance

        Returns:
            True if agent is actively speaking, False otherwise
        """
        try:
            if self._conversation_state == ConversationState.SPEAKING:
                return True

            if (activity._current_speech is not None and
                    not activity._current_speech.interrupted):
                return True

            return False

        except Exception as e:
            logger.error(f"Error detecting speech state: {e}")
            return False

    def _evaluate_interruption(self, activity, transcript: str) -> bool:
        """
        Core decision algorithm: determine if interruption should be allowed.

        Decision Logic Flow:
        1. Empty transcript → filter if speaking, allow if idle
        2. Agent idle → always allow (user has the floor)
        3. Contains interruption trigger → always allow (explicit command)
        4. All words are backchannels → filter (passive acknowledgment)
        5. Contains meaningful content → allow (active interruption)

        Args:
            activity: The AgentActivity instance
            transcript: User's speech transcription

        Returns:
            True to allow interruption, False to filter as backchannel
        """
        try:
            agent_is_speaking = self._is_agent_currently_speaking(activity)
            normalized_transcript = transcript.lower().strip()

            if not normalized_transcript:
                decision = not agent_is_speaking
                logger.debug(
                    f"Empty transcript - {'allowing' if decision else 'filtering'} "
                    f"(agent {'idle' if not agent_is_speaking else 'speaking'})"
                )
                return decision

            if not agent_is_speaking:
                logger.debug(
                    f"Agent idle, accepting input: '{normalized_transcript}'")
                return True

            tokens = self._tokenize_transcript(normalized_transcript)

            if not tokens:
                logger.debug("No valid tokens extracted - filtering")
                return False

            trigger_words = [
                token for token in tokens
                if token in self.config.interruption_triggers
            ]
            if trigger_words:
                logger.debug(
                    f"Interruption triggers detected: {trigger_words}")
                return True

            non_backchannel_tokens = [
                token for token in tokens
                if token not in self.config.backchannel_tokens
            ]

            if not non_backchannel_tokens:
                logger.debug(
                    f"Pure backchannel detected: {tokens} - filtering"
                )
                return False

            logger.debug(
                f"Meaningful tokens detected: {non_backchannel_tokens} - allowing"
            )
            return True

        except Exception as e:
            logger.error(f"Error evaluating interruption: {e}", exc_info=True)
            return True

    def _tokenize_transcript(self, transcript: str) -> List[str]:
        """
        Parse transcript into normalized tokens for analysis.

        Processing steps:
        1. Remove punctuation (except apostrophes for contractions)
        2. Split on whitespace
        3. Normalize to lowercase
        4. Filter by minimum length
        5. Remove duplicates while preserving order

        Args:
            transcript: Raw transcript text

        Returns:
            List of normalized tokens
        """
        try:
            text_only = _PUNCTUATION_PATTERN.sub(' ', transcript)
            text_only = _MULTI_SPACE_PATTERN.sub(' ', text_only)
            word_tuples = split_words(text_only, split_character=True)

            tokens = [
                word_tuple[0].lower().strip()
                for word_tuple in word_tuples
                if word_tuple[0].strip() and
                len(word_tuple[0].strip()) >= self.config.min_token_length
            ]

            seen = set()
            unique_tokens = []
            for token in tokens:
                if token not in seen:
                    seen.add(token)
                    unique_tokens.append(token)

            return unique_tokens

        except Exception as e:
            logger.error(
                f"Error tokenizing transcript '{transcript}': {e}", exc_info=True
            )
            return []

    def _intercept_vad_interrupt(self, activity) -> None:
        """
        Intercept VAD-triggered interrupts before they reach the agent.

        This is the first line of defense in the filtering pipeline. VAD detects
        audio activity faster than STT can transcribe, creating a timing gap.

        Strategy:
        1. If transcript is already available → evaluate immediately (fast path)
        2. If interruption trigger detected → execute immediately (safety)
        3. Otherwise → queue for async validation (wait for STT)

        This approach minimizes latency for interrupt commands while still
        filtering backchannels effectively.

        Args:
            activity: The AgentActivity instance
        """
        try:
            audio_recognition = self._audio_recognition_ref or activity._audio_recognition
            current_transcript = ""
            if audio_recognition is not None:
                current_transcript = audio_recognition.current_transcript or ""

            logger.debug(
                f"VAD interrupt signal: transcript='{current_transcript[:50] if current_transcript else '(pending)'}', "
                f"state={self._conversation_state.value}"
            )

            if current_transcript.strip():
                tokens = self._tokenize_transcript(current_transcript)

                if tokens and any(t in self.config.interruption_triggers for t in tokens):
                    logger.debug(
                        "Explicit interrupt command - immediate execution")
                    self._execute_immediate_interruption(activity)
                    if self._original_methods['interrupt']:
                        self._original_methods['interrupt']()
                    return

                should_allow = self._evaluate_interruption(
                    activity, current_transcript)
                if not should_allow:
                    logger.debug("Immediate filtering: backchannel detected")
                    return

                logger.debug("Valid interruption - executing")
                if self._original_methods['interrupt']:
                    self._original_methods['interrupt']()
                return

            # Herevoice detection happens before speech-to-text finishes
            logger.debug("Transcript pending - queuing for async validation")
            try:
                self._interrupt_queue.put_nowait((activity, datetime.now()))
            except asyncio.QueueFull:
                logger.warning(
                    "Interrupt queue saturated - executing immediately")
                if self._original_methods['interrupt']:
                    self._original_methods['interrupt']()

        except Exception as e:
            logger.error(
                f"Error in VAD interrupt interception: {e}", exc_info=True)
            if self._original_methods['interrupt']:
                self._original_methods['interrupt']()

    def _intercept_final_transcript(self, activity, ev, *, speaking=None):
        """
        Intercept final (complete) transcript events and filter backchannels.

        Final transcripts represent completed user utterances. This is the most
        accurate point to filter because we have the complete text. If we allow
        a backchannel to pass through here, it will trigger a full conversation
        turn and interrupt the agent.

        Filtering Strategy:
        1. Empty transcript → pass through (let LiveKit handle)
        2. Contains interruption trigger → execute immediately
        3. Pure backchannel during speech → filter completely (critical!)
        4. Otherwise → pass through to LiveKit

        Args:
            activity: The AgentActivity instance
            ev: Final transcript event from STT
            speaking: Optional speaking state parameter
        """
        try:
            if not ev.alternatives or not ev.alternatives[0].text:
                logger.debug("Final transcript event: empty")
                if self._original_methods['final_transcript']:
                    self._original_methods['final_transcript'](
                        ev, speaking=speaking)
                return

            transcript_text = ev.alternatives[0].text.lower().strip()
            logger.debug(f"Final transcript: '{transcript_text}'")

            tokens = self._tokenize_transcript(transcript_text)

            if not tokens:
                logger.debug("Final transcript: no valid tokens")
                if self._original_methods['final_transcript']:
                    self._original_methods['final_transcript'](
                        ev, speaking=speaking)
                return

            agent_is_speaking = self._is_agent_currently_speaking(activity)

            has_trigger = any(
                t in self.config.interruption_triggers for t in tokens)

            if has_trigger:
                logger.debug(
                    f"Final transcript has interruption trigger: {tokens}")
                self._execute_immediate_interruption(activity)
                if self._original_methods['final_transcript']:
                    self._original_methods['final_transcript'](
                        ev, speaking=speaking)
                return

            if agent_is_speaking and not has_trigger:
                if all(t in self.config.backchannel_tokens for t in tokens):
                    logger.debug(
                        f"Filtering backchannel from final transcript: {tokens}")

                    audio_recognition = self._audio_recognition_ref or activity._audio_recognition
                    if audio_recognition is not None:
                        try:
                            audio_recognition._audio_transcript = ""
                            audio_recognition._audio_interim_transcript = ""
                            if hasattr(audio_recognition, '_audio_preflight_transcript'):
                                audio_recognition._audio_preflight_transcript = ""
                            if hasattr(audio_recognition, '_user_turn_committed'):
                                audio_recognition._user_turn_committed = False
                            logger.debug("Cleared audio recognition state")
                        except Exception as e:
                            logger.error(f"Failed to clear audio state: {e}")

                    return

            logger.debug("Passing final transcript to LiveKit handler")
            if self._original_methods['final_transcript']:
                self._original_methods['final_transcript'](
                    ev, speaking=speaking)

        except Exception as e:
            logger.error(
                f"Error in final transcript interception: {e}", exc_info=True)
            if self._original_methods['final_transcript']:
                try:
                    self._original_methods['final_transcript'](
                        ev, speaking=speaking)
                except Exception as e2:
                    logger.error(f"Error calling original handler: {e2}")

    def _intercept_interim_transcript(self, activity, ev, *, speaking=None):
        """
        Intercept interim (partial) transcript events to prevent accumulation.

        Interim transcripts are continuously updated as the user speaks. If we
        allow backchannels to accumulate in the interim transcript buffer, they
        can cause the agent to pause or stutter. This interceptor clears them
        immediately.

        Additionally, this provides the fastest detection of interruption
        triggers - we can interrupt agent speech as soon as "stop" or "wait"
        is detected, even before the final transcript.

        Args:
            activity: The AgentActivity instance
            ev: Interim transcript event from STT
            speaking: Optional speaking state parameter
        """
        try:
            agent_is_speaking = self._is_agent_currently_speaking(activity)

            if ev.alternatives and ev.alternatives[0].text:
                transcript_text = ev.alternatives[0].text.lower().strip()
                logger.debug(
                    f"Interim transcript: '{transcript_text[:60]}...'")

                tokens = self._tokenize_transcript(transcript_text)

                if tokens:
                    has_trigger = any(
                        t in self.config.interruption_triggers for t in tokens
                    )

                    if has_trigger:
                        logger.debug(
                            f"Interim transcript has interruption trigger: {tokens}"
                        )
                        self._execute_immediate_interruption(activity)
                        if self._original_methods['interim_transcript']:
                            self._original_methods['interim_transcript'](
                                ev, speaking=speaking
                            )
                        return

                    # This prevents stuttering and pauses
                    if agent_is_speaking and all(
                        t in self.config.backchannel_tokens for t in tokens
                    ):
                        logger.debug(
                            f"Filtering backchannel from interim transcript: {tokens}"
                        )

                        audio_recognition = (
                            self._audio_recognition_ref or
                            activity._audio_recognition
                        )
                        if audio_recognition is not None:
                            try:
                                audio_recognition._audio_interim_transcript = ""
                                logger.debug(
                                    "Cleared interim transcript buffer")
                            except Exception as e:
                                logger.error(
                                    f"Failed to clear interim buffer: {e}")

                        return

            if self._original_methods['interim_transcript']:
                self._original_methods['interim_transcript'](
                    ev, speaking=speaking)

        except Exception as e:
            logger.error(
                f"Error in interim transcript interception: {e}", exc_info=True
            )
            if self._original_methods['interim_transcript']:
                try:
                    self._original_methods['interim_transcript'](
                        ev, speaking=speaking)
                except Exception as e2:
                    logger.error(f"Error calling original handler: {e2}")

    def _intercept_turn_ending(self, activity, info):
        """
        Intercept turn ending events to prevent unwanted conversation turns.

        This is the final checkpoint before a user utterance becomes a full
        conversation turn that the agent must respond to. Backchannels must
        be filtered here to prevent the agent from responding to "yeah" with
        "How can I help you?"

        Decision Logic:
        1. No transcript → defer to LiveKit
        2. Contains interruption trigger → prevent turn (already handled)
        3. Pure backchannel during speech → prevent turn
        4. Otherwise → allow turn

        Args:
            activity: The AgentActivity instance
            info: Turn ending info from LiveKit

        Returns:
            True to allow turn completion, False to prevent
        """
        try:
            if not hasattr(info, 'new_transcript') or not info.new_transcript:
                logger.debug("Turn ending: no transcript")
                if self._original_methods['end_of_turn']:
                    return self._original_methods['end_of_turn'](info)
                return True

            transcript_text = info.new_transcript.lower().strip()
            logger.debug(f"Turn ending: '{transcript_text}'")

            tokens = self._tokenize_transcript(transcript_text)

            if not tokens:
                logger.debug("Turn ending: no valid tokens")
                if self._original_methods['end_of_turn']:
                    return self._original_methods['end_of_turn'](info)
                return True

            agent_is_speaking = self._is_agent_currently_speaking(activity)

            has_trigger = any(
                t in self.config.interruption_triggers for t in tokens)

            if has_trigger:
                logger.debug(
                    f"Turn ending: interruption trigger → preventing turn")
                self._execute_immediate_interruption(activity)
                return False

            if agent_is_speaking and not has_trigger:
                if all(t in self.config.backchannel_tokens for t in tokens):
                    logger.debug(
                        f"Turn ending: pure backchannel → preventing turn")
                    return False

            logger.debug("Turn ending: valid turn → allowing")
            if self._original_methods['end_of_turn']:
                return self._original_methods['end_of_turn'](info)
            return True

        except Exception as e:
            logger.error(
                f"Error in turn ending interception: {e}", exc_info=True)
            if self._original_methods['end_of_turn']:
                try:
                    return self._original_methods['end_of_turn'](info)
                except Exception as e2:
                    logger.error(f"Error calling original handler: {e2}")
            return True


    def shutdown(self) -> None:
        """
        Gracefully shutdown the contextual speech filter and release resources.

        Cancels async tasks and clears references.
        """
        try:
            logger.info("Initiating ContextualSpeechFilter shutdown")

            if self._validation_worker and not self._validation_worker.done():
                self._validation_worker.cancel()
                logger.debug("Cancelled validation worker task")

            self._session_ref = None
            self._activity_ref = None
            self._audio_recognition_ref = None

            logger.info("ContextualSpeechFilter shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


agent_server = AgentServer()


@agent_server.rtc_session()
async def agent_entrypoint(context: JobContext):
    """
    Main entrypoint for the contextual speech filtering voice agent.

    This agent demonstrates advanced interruption handling that distinguishes
    between passive acknowledgments (backchanneling) and active interruptions
    based on conversation context.

    Features:
        - Context-aware speech filtering
        - Sub-300ms interruption validation latency
        - Configurable backchannel and trigger word sets
        - Robust error handling

    Args:
        context: LiveKit job context containing room and participant info
    """
    logger.info("Initializing contextual speech agent")

    session = AgentSession(
        vad=silero.VAD.load(),
        llm="google/gemini-2.5-flash-lite",
        stt=deepgram.STT(),
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        false_interruption_timeout=1.0,  
        resume_false_interruption=True,  
        min_interruption_words=0,        
    )

    speech_filter = ContextualSpeechFilter(
        backchannel_words=[
            "yeah", "ok", "hmm", "right", "uh-huh", "aha", "yep", "okay",
            "uh", "um", "mm-hmm", "mhm",
            "yes", "sure", "alright", "yup", "correct", "gotcha", "roger",
            "indeed", "exactly", "absolutely", "understood",
            "see", "true", "agreed", "fine", "good", "nice", "great",
            "wow", "oh", "ah",
            "i", "know", "get", "it",
        ],
        interruption_commands=[
            "stop", "wait", "no", "halt", "pause", "cancel", "hold"
        ],
        validation_timeout=0.3,      
        min_word_length=1,           
    )

    speech_filter.install(session)

    await session.start(
        agent=Agent(
            instructions=(
                "You are a knowledgeable and articulate assistant. When providing "
                "explanations or detailed information, maintain your flow and continue "
                "speaking naturally even if the user says brief acknowledgments like "
                "'yeah', 'ok', 'hmm', or 'right'. These are signals that they're "
                "listening, not requests to stop.\n\n"
                "However, if the user says 'stop', 'wait', 'no', 'halt', or 'pause', "
                "stop speaking immediately and listen to their input.\n\n"
                "When the user is silent or you finish speaking, treat any input "
                "including 'yeah' or 'ok' as normal conversation that deserves a response."
            )
        ),
        room=context.room,
    )

    logger.info("Contextual speech agent started successfully")


if __name__ == "__main__":
    logger.info("Starting LiveKit agent server")
    cli.run_app(agent_server)
