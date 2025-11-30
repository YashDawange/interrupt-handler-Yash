import asyncio
import logging
import os
import re
from typing import List, Set
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.agents.tokenize.basic import split_words
from livekit.plugins import cartesia, deepgram, openai, silero
from dotenv import load_dotenv

pregex = re.compile(r"[^\w\s-]")
logger = logging.getLogger(__name__)
load_dotenv()


class AgentSpeechManager:
    """
    Manages agent speech interruptions from user backchanneling.

    This filter prevents user affirmations (e.g., "yeah", "okay") from
    interrupting the agent, while allowing explicit commands (e.g., "stop")
    to work as expected.

    Warning:
        This relies on patching internal `AgentSession` methods, which may
        break in future `livekit-agents` updates.
    """

    def __init__(
        self,
        ignorable_phrases: List[str] | None = None,
        stop_phrases: List[str] | None = None,
    ):
        """
        Initializes the speech manager.

        Args:
            ignorable_phrases: Regex patterns for words to ignore.
            stop_phrases: Words that should always trigger an interruption.
        """
        if ignorable_phrases:
            self.ignorable_phrase_patterns = [
                re.compile(p, re.IGNORECASE) for p in ignorable_phrases
            ]
        else:
            default_patterns = [
                r"yeah?", r"ok(ay)?", r"h+m+", r"right", r"uh-?huh", r"aha", r"yep",
                r"uh+", r"um+", r"mm-?hmm+", r"yes", r"sure", "got it", r"alright",
                r"mhm+", r"yup", r"correct", r"gotcha", r"roger", r"indeed",
                r"exactly", r"absolutely", r"understood", r"see", r"true",
                r"agreed", r"fine", "good", "nice", "great", "wow", "oh",
            ]
            self.ignorable_phrase_patterns = [
                re.compile(p, re.IGNORECASE) for p in default_patterns
            ]

        self.stop_phrases: Set[str] = (
            {w.lower() for w in stop_phrases}
            if stop_phrases
            else {"stop", "wait", "no", "halt", "pause", "cancel"}
        )

        self._session: AgentSession | None = None
        self._activity = None
        self._agent_state = "idle"
        self._word_cache: dict[str, List[str]] = {}
        self._original_methods = {}

    def attach(self, session: AgentSession):
        """
        Attaches the manager to an `AgentSession`.
        """
        self._session = session
        session.on("agent_state_changed", self._monitor_state)
        asyncio.create_task(self._patch_internals())

    async def _patch_internals(self):
        """
        Waits for the internal AgentActivity and applies method overrides.
        """
        try:
            self._activity = await self._find_activity_monitor()
        except asyncio.TimeoutError:
            logger.error("Failed to find AgentActivity. The filter will be inactive.")
            return

        self._override_method("_interrupt_by_audio_activity", self._handle_audio)
        self._override_method("on_final_transcript", self._handle_final_text)
        self._override_method("on_interim_transcript", self._handle_interim_text)
        self._override_method("on_end_of_turn", self._handle_turn_end)

        if self._original_methods:
            logger.info("Speech manager installed.")
        else:
            logger.error("Could not install speech manager.")

    async def _find_activity_monitor(self, timeout: float = 5.0):
        """Waits for and returns the session's activity monitor."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if hasattr(self._session, "_activity") and self._session._activity is not None:
                return self._session._activity
            await asyncio.sleep(0.05)
        raise asyncio.TimeoutError()

    def _override_method(self, name: str, new_method):
        """
        Replaces a method on the activity object and stores the original.
        """
        if hasattr(self._activity, name):
            original = getattr(self._activity, name)
            self._original_methods[name] = original
            setattr(self._activity, name, new_method)
        else:
            logger.warning(f"Cannot override '{name}': attribute not found.")

    def _monitor_state(self, state_event):
        """Tracks the agent's speaking state."""
        self._agent_state = state_event.new_state

    def _split_to_words(self, transcript: str) -> List[str]:
        """Splits a transcript into a list of words, with caching."""
        words_only = pregex.sub(" ", transcript)
        if transcript in self._word_cache:
            return self._word_cache[transcript]

        word_tuples = split_words(words_only, split_character=True)
        words = [w[0].lower().strip() for w in word_tuples if w[0].strip()]

        if len(self._word_cache) > 100:
            self._word_cache.pop(next(iter(self._word_cache)))
        self._word_cache[transcript] = words
        return words

    def _is_only_backchannel(self, words: List[str]) -> bool:
        """Checks if words are only ignorable affirmations."""
        if not words:
            return False
        return all(self._is_ignorable_term(word) for word in words)

    def _is_ignorable_term(self, word: str) -> bool:
        """Checks if a word matches an ignorable pattern."""
        for pattern in self.ignorable_phrase_patterns:
            if pattern.fullmatch(word):
                return True
        return False

    @property
    def _is_agent_currently_speaking(self) -> bool:
        """Checks if the agent is currently speaking."""
        if self._activity is None:
            return False

        is_speaking_state = self._agent_state == "speaking"
        has_current_speech = (
            hasattr(self._activity, '_current_speech') and
            self._activity._current_speech is not None and
            not self._activity._current_speech.interrupted
        )
        return is_speaking_state or has_current_speech

    def _force_stop(self):
        """Stops the agent's speech and clears the user turn."""
        if self._activity is None:
            return

        if hasattr(self._activity, '_current_speech') and self._activity._current_speech:
            self._activity._current_speech.interrupt(force=True)

        if hasattr(self._activity, '_preemptive_generation') and self._activity._preemptive_generation:
            if hasattr(self._activity._preemptive_generation, 'speech_handle') and \
               hasattr(self._activity._preemptive_generation.speech_handle, '_cancel'):
                self._activity._preemptive_generation.speech_handle._cancel()
            self._activity._preemptive_generation = None

        if self._session:
            self._session.clear_user_turn()

        self._clear_stt_cache()

    def _clear_stt_cache(self):
        """Clears internal STT transcripts."""
        if self._activity and hasattr(self._activity, '_audio_recognition'):
            audio_recognition = self._activity._audio_recognition
            if audio_recognition:
                audio_recognition._audio_transcript = ""
                audio_recognition._audio_interim_transcript = ""

    def _handle_audio(self):
        """
        Processes a raw audio signal, deferring interruption.
        """
        transcript = ""
        if self._activity and hasattr(self._activity, '_audio_recognition'):
            audio_rec = self._activity._audio_recognition
            if audio_rec:
                transcript = audio_rec.current_transcript or ""

        words = self._split_to_words(transcript)

        if self._is_agent_currently_speaking and not transcript.strip():
            return

        if self._is_agent_currently_speaking and self._is_only_backchannel(words):
            return

        original = self._original_methods.get("_interrupt_by_audio_activity")
        if original:
            original()

    def _handle_final_text(self, transcript_event, *, speaking=None):
        """
        Processes a final transcript.
        """
        original = self._original_methods.get("on_final_transcript")
        if not (transcript_event.alternatives and transcript_event.alternatives[0].text):
            if original:
                original(transcript_event, speaking=speaking)
            return

        transcript = transcript_event.alternatives[0].text.strip()
        words = self._split_to_words(transcript)

        if not words:
            if original:
                original(transcript_event, speaking=speaking)
            return

        if any(word in self.stop_phrases for word in words):
            self._force_stop()
            if original:
                original(transcript_event, speaking=speaking)
            return
        elif self._is_agent_currently_speaking and self._is_only_backchannel(words):
            self._clear_stt_cache()
            return

        if original:
            original(transcript_event, speaking=speaking)

    def _handle_interim_text(self, transcript_event, *, speaking=None):
        """
        Processes an interim transcript.
        """
        original = self._original_methods.get("on_interim_transcript")
        if transcript_event.alternatives and transcript_event.alternatives[0].text:
            transcript = transcript_event.alternatives[0].text.strip()
            words = self._split_to_words(transcript)

            if words:
                if any(word in self.stop_phrases for word in words):
                    self._force_stop()
                    if original:
                        original(transcript_event, speaking=speaking)
                    return
                elif self._is_agent_currently_speaking and self._is_only_backchannel(words):
                    if self._activity and hasattr(self._activity, '_audio_recognition'):
                        audio_rec = self._activity._audio_recognition
                        if audio_rec:
                            audio_rec._audio_interim_transcript = ""
                    return

        if original:
            original(transcript_event, speaking=speaking)

    def _handle_turn_end(self, turn_info) -> bool:
        """
        Validates turn completion.
        """
        original = self._original_methods.get("on_end_of_turn", lambda _: True)

        if not turn_info.new_transcript:
            return original(turn_info)

        words = self._split_to_words(turn_info.new_transcript.strip())
        if not words:
            return original(turn_info)

        if any(word in self.stop_phrases for word in words):
            self._force_stop()
            return False

        if self._is_agent_currently_speaking and self._is_only_backchannel(words):
            return False

        return original(turn_info)


server = AgentServer()


@server.rtc_session()
async def session_entrypoint(job: JobContext):
    """
    Agent entrypoint demonstrating contextual interruption handling.
    """
    session = AgentSession(
        vad=silero.VAD.load(),
        llm="openai/gpt-4.1-mini",
        stt="deepgram/nova-3",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        false_interruption_timeout=None,
        min_interruption_words=1,
    )

    ignore_words_str = os.getenv("LIVEKIT_IGNORE_WORDS")
    interrupt_words_str = os.getenv("LIVEKIT_INTERRUPT_WORDS")

    ignorable_phrases = ignore_words_str.split(',') if ignore_words_str else None
    stop_phrases = interrupt_words_str.split(',') if interrupt_words_str else None

    speech_manager = AgentSpeechManager(
        ignorable_phrases=ignorable_phrases,
        stop_phrases=stop_phrases,
    )
    speech_manager.attach(session)

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