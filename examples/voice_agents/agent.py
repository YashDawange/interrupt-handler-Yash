import asyncio
import logging
import re
from typing import List, Set

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.agents.tokenize.basic import split_words
from livekit.plugins import cartesia, deepgram, google, silero

logger = logging.getLogger("interrupt-handler-agent")

load_dotenv()

# Pre-compile regex for performance
_PUNCTUATION_REGEX = re.compile(r'[^\w\s]')


class IntelligentInterruptHandler:
    """
    Intelligent interruption handler that filters out backchanneling words
    when the agent is speaking, while allowing valid interruptions.
    """

    def __init__(
        self,
        ignore_words: List[str] | None = None,
        interrupt_commands: List[str] | None = None,
        validation_timeout: float = 0.3,
    ):
        """
        Initialize the interrupt handler.
        Args:
            ignore_words: List of backchanneling words to ignore when agent is speaking.
                         Default: ['yeah', 'ok', 'hmm', 'right', 'uh-huh', 'aha', 'yep', 'okay']
            interrupt_commands: List of words that should always interrupt.
                               Default: ['stop', 'wait', 'no', 'halt']
            validation_timeout: Maximum time to wait for STT transcript before making decision.
                               Default: 0.3s
        """
        if ignore_words:
            self.ignore_words: Set[str] = {w.lower() for w in ignore_words}
        else:
            self.ignore_words: Set[str] = {
                "yeah", "ok", "hmm", "right", "uh-huh", "aha", "yep", "okay", "uh", "um", "mm-hmm"
            }

        if interrupt_commands:
            self.interrupt_commands: Set[str] = {w.lower() for w in interrupt_commands}
        else:
            self.interrupt_commands: Set[str] = {
                "stop", "wait", "no", "halt", "pause", "cancel"
            }

        self.validation_timeout = validation_timeout
        self._original_interrupt_method = None
        self._original_on_final_transcript = None
        self._original_on_interim_transcript = None
        self._original_on_end_of_turn = None
        self._original_user_turn_completed_task = None
        self._agent_state = "idle"
        self._current_transcript = ""
        self._session = None
        self._activity = None
        self._audio_recognition = None

        # Cache for word processing to reduce allocations
        self._word_cache: dict[str, List[str]] = {}

    def setup(self, session: AgentSession) -> None:
        """
        Set up the interrupt handler by monkey-patching the AgentActivity.
        
        Args:
            session: The AgentSession instance to patch
        """
        # Store session reference for clearing turns
        self._session = session

        # Set up event listeners first (they work immediately)
        session.on("agent_state_changed", self._on_agent_state_changed)
        session.on("user_input_transcribed", self._on_user_input_transcribed)

        # Wait for activity to be initialized using event-based approach
        async def _setup_after_start():
            # Use a more efficient approach: wait for activity with timeout
            max_wait_time = 2.0
            check_interval = 0.05
            elapsed = 0.0

            while elapsed < max_wait_time:
                if session._activity is not None:
                    break
                await asyncio.sleep(check_interval)
                elapsed += check_interval

            if session._activity is None:
                logger.error("Failed to find AgentActivity, interrupt handler not installed")
                return

            activity = session._activity
            self._activity = activity
            # Cache audio recognition reference to avoid deep traversal
            self._audio_recognition = activity._audio_recognition

            # Store original methods
            self._original_interrupt_method = activity._interrupt_by_audio_activity
            self._original_on_final_transcript = activity.on_final_transcript
            self._original_on_interim_transcript = activity.on_interim_transcript
            self._original_on_end_of_turn = activity.on_end_of_turn
            self._original_user_turn_completed_task = activity._user_turn_completed_task

            # Create wrapper methods that capture activity
            def _interrupt_by_audio_activity_wrapper():
                return self._interrupt_by_audio_activity_wrapper(activity)

            def _on_final_transcript_wrapper(ev, *, speaking=None):
                return self._on_final_transcript_wrapper(activity, ev, speaking=speaking)

            def _on_interim_transcript_wrapper(ev, *, speaking=None):
                return self._on_interim_transcript_wrapper(activity, ev, speaking=speaking)

            def _on_end_of_turn_wrapper(info):
                return self._on_end_of_turn_wrapper(activity, info)

            def _user_turn_completed_task_wrapper(old_task, info):
                return self._user_turn_completed_task_wrapper(activity, old_task, info)

            # Replace the methods
            activity._interrupt_by_audio_activity = _interrupt_by_audio_activity_wrapper
            activity.on_final_transcript = _on_final_transcript_wrapper
            activity.on_interim_transcript = _on_interim_transcript_wrapper
            activity.on_end_of_turn = _on_end_of_turn_wrapper
            activity._user_turn_completed_task = _user_turn_completed_task_wrapper

            logger.info("Intelligent interrupt handler installed successfully")

        # Schedule setup task
        asyncio.create_task(_setup_after_start())

    def _on_agent_state_changed(self, ev) -> None:
        """Track agent state changes."""
        self._agent_state = ev.new_state
        # Reduced logging frequency - only log state transitions, not every change
        if ev.new_state in ("speaking", "listening", "thinking"):
            logger.debug(f"Agent state: {self._agent_state}")

    def _on_user_input_transcribed(self, ev) -> None:
        """Track user transcript updates."""
        if ev.transcript:
            self._current_transcript = ev.transcript
            # Reduced logging - only log final transcripts
            if ev.is_final:
                logger.debug(f"Final transcript: {self._current_transcript[:50]}")

    def _should_interrupt(self, activity, transcript: str) -> bool:
        """
        Determine if interruption should proceed based on agent state and transcript.
        
        Args:
            activity: The AgentActivity instance
            transcript: Current user transcript
            
        Returns:
            True if interruption should proceed, False otherwise
        """
        # Check if agent is currently speaking
        is_agent_speaking = (
            self._agent_state == "speaking"
            or (activity._current_speech is not None and not activity._current_speech.interrupted)
        )

        # Normalize transcript
        transcript_lower = transcript.lower().strip()

        if not transcript_lower:
            # Empty transcript - when agent is speaking, don't interrupt on empty transcript
            # This handles the VAD/STT timing issue - VAD triggers before STT has transcript
            if is_agent_speaking:
                logger.debug("Empty transcript while agent speaking - preventing interruption (waiting for STT)")
                return False
            # Agent not speaking - allow interruption (normal flow)
            return True

        if not is_agent_speaking:
            # Agent is not speaking - always allow interruption (normal conversation flow)
            return True

        # Agent is speaking - analyze transcript content with context awareness
        # Use cached word processing to reduce allocations
        words_lower = self._process_words(transcript_lower)

        if not words_lower:
            # No words detected yet - prevent interruption (waiting for STT to provide transcript)
            return False

        # Fast path: check for interrupt commands first (highest priority)
        if any(word in self.interrupt_commands for word in words_lower):
            return True

        # Fast path: check if ALL words are backchanneling (most common case)
        if all(word in self.ignore_words for word in words_lower):
            # Only backchanneling words - prevent interruption
            return False

        # Context-aware check: filter out backchanneling and check for meaningful content
        meaningful_words = [w for w in words_lower if w not in self.ignore_words]

        # If meaningful words exist, allow interruption
        if meaningful_words:
            return True

        # Fallback: allow interruption (safer to interrupt than miss important input)
        return True

    def _process_words(self, transcript: str) -> List[str]:
        """
        Process transcript into words list with caching to reduce allocations.
        """
        # Use cache for repeated transcripts
        if transcript in self._word_cache:
            return self._word_cache[transcript]

        # Normalize: remove punctuation
        words_only = _PUNCTUATION_REGEX.sub(' ', transcript)
        word_tuples = split_words(words_only, split_character=True)
        words_lower = [w[0].lower().strip() for w in word_tuples if w[0].strip()]

        # Cache result (limit cache size to prevent memory issues)
        if len(self._word_cache) < 100:
            self._word_cache[transcript] = words_lower

        return words_lower

    def _interrupt_by_audio_activity_wrapper(self, activity) -> None:
        """
        Wrapper for the original _interrupt_by_audio_activity method.
        Adds intelligent filtering before calling the original method.
        """
        # Use cached audio recognition reference
        audio_recognition = self._audio_recognition or activity._audio_recognition
        transcript = ""
        if audio_recognition is not None:
            transcript = audio_recognition.current_transcript or ""

        # Check if we should interrupt
        should_interrupt = self._should_interrupt(activity, transcript)

        if not should_interrupt:
            # Prevent interruption - agent should continue speaking
            return

        # Allow interruption - call original method
        if self._original_interrupt_method:
            self._original_interrupt_method()

    def _on_final_transcript_wrapper(self, activity, ev, *, speaking=None):
        """
        Wrapper for on_final_transcript that prevents processing backchanneling words
        when the agent is speaking. This intercepts BEFORE the event is emitted.
        """
        if not ev.alternatives or not ev.alternatives[0].text:
            # No transcript - allow normal processing
            if self._original_on_final_transcript:
                self._original_on_final_transcript(ev, speaking=speaking)
            return

        transcript = ev.alternatives[0].text.lower().strip()
        words_lower = self._process_words(transcript)

        if not words_lower:
            # No words - allow normal processing
            if self._original_on_final_transcript:
                self._original_on_final_transcript(ev, speaking=speaking)
            return

        # Check if agent is currently speaking
        is_agent_speaking = (
            self._agent_state == "speaking"
            or (activity._current_speech is not None and not activity._current_speech.interrupted)
        )

        # Fast path: check for interrupt commands first
        has_interrupt_command = any(word in self.interrupt_commands for word in words_lower)

        if has_interrupt_command:
            # Check if transcript contains ONLY interrupt commands
            all_interrupt_commands = all(word in self.interrupt_commands for word in words_lower)

            if all_interrupt_commands:
                # Only interrupt commands - clear turn, don't generate response
                # Use cached audio recognition reference
                audio_recognition = self._audio_recognition or activity._audio_recognition
                if audio_recognition is not None:
                    audio_recognition._audio_transcript = ""
                    audio_recognition._audio_interim_transcript = ""
                    audio_recognition._audio_preflight_transcript = ""
                    audio_recognition._user_turn_committed = False

                # Remove matching message from chat context if present
                self._remove_message_from_chat_context(activity, ev.alternatives[0].text)

                # Don't call original method - prevents event emission and turn completion
                return

        if is_agent_speaking and not has_interrupt_command:
            # Agent is speaking - check for backchanneling
            # Fast path: check if all words are backchanneling
            if all(word in self.ignore_words for word in words_lower):
                # Only backchanneling words - prevent ALL processing
                # Use cached audio recognition reference
                audio_recognition = self._audio_recognition or activity._audio_recognition
                if audio_recognition is not None:
                    audio_recognition._audio_transcript = ""
                    audio_recognition._audio_interim_transcript = ""
                    audio_recognition._audio_preflight_transcript = ""
                    audio_recognition._user_turn_committed = False
                # Don't call original method - prevents event emission and all processing
                return

        # Allow normal processing - call original method
        if self._original_on_final_transcript:
            self._original_on_final_transcript(ev, speaking=speaking)

    def _on_interim_transcript_wrapper(self, activity, ev, *, speaking=None):
        """
        Wrapper for on_interim_transcript that prevents accumulation of backchanneling words
        when the agent is speaking.
        """
        # Check if agent is currently speaking
        is_agent_speaking = (
            self._agent_state == "speaking"
            or (activity._current_speech is not None and not activity._current_speech.interrupted)
        )

        if is_agent_speaking and ev.alternatives and ev.alternatives[0].text:
            transcript = ev.alternatives[0].text.lower().strip()
            words_lower = self._process_words(transcript)

            if not words_lower:
                return

            # Fast path: check for interrupt commands first
            has_interrupt_command = any(word in self.interrupt_commands for word in words_lower)
            if not has_interrupt_command:
                # Fast path: check if all words are backchanneling
                if all(word in self.ignore_words for word in words_lower):
                    # Only backchanneling words - prevent accumulation
                    # Use cached audio recognition reference
                    audio_recognition = self._audio_recognition or activity._audio_recognition
                    if audio_recognition is not None:
                        audio_recognition._audio_interim_transcript = ""
                    # Don't call original method - prevents event emission
                    return

        # Allow normal processing - call original method
        if self._original_on_interim_transcript:
            self._original_on_interim_transcript(ev, speaking=speaking)

    def _on_end_of_turn_wrapper(self, activity, info):
        """
        Wrapper for on_end_of_turn that prevents turn completion when only
        backchanneling words or interrupt commands are detected.
        """
        if not info.new_transcript:
            # No transcript - allow normal processing
            if self._original_on_end_of_turn:
                return self._original_on_end_of_turn(info)
            return True

        transcript = info.new_transcript.lower().strip()
        words_lower = self._process_words(transcript)

        if not words_lower:
            # No words - allow normal processing
            if self._original_on_end_of_turn:
                return self._original_on_end_of_turn(info)
            return True

        # Check if agent is currently speaking
        is_agent_speaking = (
            self._agent_state == "speaking"
            or (activity._current_speech is not None and not activity._current_speech.interrupted)
        )

        # Fast path: check for interrupt commands first
        has_interrupt_command = any(word in self.interrupt_commands for word in words_lower)

        if has_interrupt_command:
            # Fast path: check if ALL words are interrupt commands
            if all(word in self.interrupt_commands for word in words_lower):
                # Only interrupt commands - prevent turn completion
                return False

        if is_agent_speaking and not has_interrupt_command:
            # Fast path: check if all words are backchanneling
            if all(word in self.ignore_words for word in words_lower):
                # Only backchanneling words - prevent turn completion
                return False

        # Allow normal processing - call original method
        if self._original_on_end_of_turn:
            return self._original_on_end_of_turn(info)
        return True

    def _remove_message_from_chat_context(self, activity, transcript_text: str) -> None:
        """
        Remove matching message from chat context if present.
        Optimized to avoid repeated attribute lookups.
        """
        if not activity._agent or not activity._agent._chat_ctx:
            return

        chat_items = activity._agent._chat_ctx.items
        if not chat_items:
            return

        transcript_lower = transcript_text.lower().strip()
        # Check last few items (most recent are at the end)
        for i in range(len(chat_items) - 1, max(-1, len(chat_items) - 4), -1):
            item = chat_items[i]
            if (hasattr(item, 'role') and item.role == "user" and
                hasattr(item, 'content') and item.content):
                item_content = item.content[0] if isinstance(item.content, list) else str(item.content)
                if item_content.lower().strip() == transcript_lower:
                    chat_items.pop(i)
                    break

    async def _user_turn_completed_task_wrapper(self, activity, old_task, info):
        """
        Wrapper for _user_turn_completed_task that prevents adding interrupt-only
        commands to chat context.
        """
        if info.new_transcript:
            transcript = info.new_transcript.lower().strip()
            words_lower = self._process_words(transcript)

            if words_lower:
                # Fast path: check if ALL words are interrupt commands
                if all(word in self.interrupt_commands for word in words_lower):
                    # Only interrupt commands - clear transcript and remove from chat context
                    info.new_transcript = ""
                    self._remove_message_from_chat_context(activity, transcript)

        # Call original method
        if self._original_user_turn_completed_task:
            return await self._original_user_turn_completed_task(old_task, info)


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """
    Entrypoint for the intelligent interrupt handler agent.
    This agent demonstrates context-aware interruption handling.
    """
    session = AgentSession(
        vad=silero.VAD.load(),
        llm="google/gemini-2.5-flash-lite",
        stt=deepgram.STT(),
        tts=cartesia.TTS(),
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
        min_interruption_words=0,  # We handle word filtering ourselves
    )

    # Create and set up interrupt handler
    interrupt_handler = IntelligentInterruptHandler(
        ignore_words=["yeah", "ok", "hmm", "right", "uh-huh", "aha", "yep", "okay", "uh", "um", "mm-hmm"],
        interrupt_commands=["stop", "wait", "no", "halt", "pause", "cancel"],
        validation_timeout=0.3,
    )

    interrupt_handler.setup(session)

    await session.start(
        agent=Agent(
            instructions=(
                "You are a helpful assistant. When explaining something, "
                "speak clearly and continue your explanation even if the user "
                "says brief acknowledgements like 'yeah' or 'ok'. Only stop if "
                "they explicitly say 'stop', 'wait', or 'no'."
            )
        ),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)