import asyncio
import logging
import os
import re
import time
from typing import Set, Optional

from dotenv import load_dotenv

# LiveKit imports (same as your original file)
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    UserInputTranscribedEvent,
    cli,
    room_io,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("backchannel-agent")
logger.setLevel(logging.INFO)
# optional: add a simple console handler if running standalone
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(ch)

load_dotenv()


def _parse_word_list(env_value: str | None) -> Set[str]:
    if not env_value:
        return set()

    return {w.strip().lower() for w in env_value.split(",") if w.strip()}


class BackchannelFilter:
 
    BACKGROUND_VALIDATE_TIMEOUT = 1.0

    def __init__(self, session: AgentSession) -> None:
        self._session = session

        # default ignore (backchannel) words
        default_ignore = {
            "yeah",
            "ok",
            "okay",
            "hmm",
            "mm",
            "mmm",
            "uh",
            "uhh",
            "uh-huh",
            "mhm",
            "right",
            "sure",
            "yep",
            "yup",
        }

        # default interrupt words
        default_interrupt = {"stop", "wait", "hold", "holdon", "no", "nope", "waitt"}

        self._ignore_words: Set[str] = default_ignore | _parse_word_list(
            os.getenv("BACKCHANNEL_IGNORE_WORDS")
        )
        self._interrupt_words: Set[str] = default_interrupt | _parse_word_list(
            os.getenv("BACKCHANNEL_INTERRUPT_WORDS")
        )


        self._agent_speaking = False

      
        self._lock = asyncio.Lock()

      
        self._last_bg_task: Optional[asyncio.Task] = None

    def attach(self) -> None:
        """
        Attach handlers to the session's events.
        We listen to both transcription events and (if available) speech lifecycle events.
        """
        # transcription events (interim + final)
        self._session.on("user_input_transcribed", self._on_user_input_transcribed)

        try:
            self._session.on("speech_started", self._on_speech_started)
            self._session.on("speech_ended", self._on_speech_ended)
        except Exception:
            logger.debug("speech lifecycle events not available; will use session.current_speech fallback")

    def _on_speech_started(self, *_args, **_kwargs) -> None:
        self._agent_speaking = True
        logger.debug("Agent speech started → speaking flag True")

    def _on_speech_ended(self, *_args, **_kwargs) -> None:
        self._agent_speaking = False
        logger.debug("Agent speech ended → speaking flag False")

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize to capture normal words and repeated letters (stoppp, nooo).
        Keeps only alphabetic sequences to match against our word lists.
        """
    
        toks = re.findall(r"[a-zA-Z]+", text.lower())
        return toks

    def _contains_interrupt_word(self, tokens: list[str]) -> bool:
        """
        Returns True if any token matches or starts with an interrupt word.
        We use startswith to capture elongated tokens (e.g., 'nooo', 'stoppp').
        """
        for tok in tokens:
            if tok in self._interrupt_words:
                return True
            for base in self._interrupt_words:
                if tok.startswith(base):
                    return True
        return False

    def _is_only_acknowledgement(self, tokens: list[str]) -> bool:
        """
        Return True if all tokens (non-empty) are in the ignore words set.
        Example: "yeah", "uh-huh", "okay" => True
        """
        if not tokens:
            return False
        return all(tok in self._ignore_words for tok in tokens)

    def _is_agent_speaking(self) -> bool:
        """
        Robust check whether the agent is currently speaking.
        Prefer the lifecycle flag (if available), otherwise query session.current_speech.
        """
        try:
            # prefer the tracked flag if it was set by events
            if self._agent_speaking:
                return True
        except Exception:
            pass

        try:
            # fallback to session.current_speech if present
            cur = getattr(self._session, "current_speech", None)
            if cur is not None:
                # 'interrupted' attribute used in your original code to check if stopped
                interrupted = getattr(cur, "interrupted", False)
                return not interrupted
        except Exception:
            # best-effort: assume speaking False
            pass

        return False

    def _schedule_bg_validation(self, text: str, tokens: list[str], ev: UserInputTranscribedEvent):
        """
        Schedule a small asynchronous validator that can optionally re-evaluate within
        a short window (BACKGROUND_VALIDATE_TIMEOUT). This helps with race conditions
        where VAD paused the agent before STT delivered a final transcription.

        The actual handler is `self._bg_validate`.
        """
        # cancel previous task if it's still running (we keep only the latest)
        if self._last_bg_task and not self._last_bg_task.done():
            try:
                self._last_bg_task.cancel()
            except Exception:
                pass

        task = asyncio.create_task(self._bg_validate(text, tokens, ev))
        self._last_bg_task = task

    async def _bg_validate(self, text: str, tokens: list[str], ev: UserInputTranscribedEvent):
        """
        Runs in the background; we do a quick check and decide.
        Ev can be interim or final. We attempt to react immediately for interim
        if we have enough signal (interrupt or pure ack).
        Otherwise we allow up to BACKGROUND_VALIDATE_TIMEOUT to wait for finalization.
        """
        async with self._lock:
            try:
                # If this event is interim, try immediate fast responses:
                if not ev.is_final:
                    # FAST PATH: if there's an interrupt token present, stop right away.
                    if self._contains_interrupt_word(tokens):
                        logger.info("🛑 (interim) detected interrupt word in: %r", text)
                        try:
                            self._session.interrupt(force=True)
                        except Exception as e:
                            logger.exception("interrupt failed: %s", e)
                        return

                    # FAST PATH: if it's pure ack-only, we can clear the user turn immediately
                    # to avoid any pause. Do that only if agent is speaking now.
                    if self._is_only_acknowledgement(tokens) and self._is_agent_speaking():
                        logger.info("✓ (interim) pure ack detected while speaking: %r → continue", text)
                        try:
                            # clear_user_turn tells the session to treat this user audio as non-turn
                            # and resume the agent speech seamlessly.
                            self._session.clear_user_turn()
                        except Exception:
                            # clear_user_turn isn't critical; swallow errors
                            logger.exception("clear_user_turn failed (interim)")
                        return

                    # If we reach here, we didn't have a decisive interim signal.
                    # Wait a small amount for a final transcript (bounded)
                    # If the event is interim, wait up to BACKGROUND_VALIDATE_TIMEOUT seconds
                    start = time.monotonic()
                    elapsed = 0.0
                    while elapsed < self.BACKGROUND_VALIDATE_TIMEOUT:
                        # give the event loop a little breathing room
                        await asyncio.sleep(0.08)
                        elapsed = time.monotonic() - start

                        # If session is no longer speaking, no special handling required here
                        # (the turn will be processed normally).
                        if not self._is_agent_speaking():
                            logger.debug("Agent no longer speaking while validating (%s elapsed); aborting bg validate", elapsed)
                            return

                        # If a final transcript for the same user input arrives, we expect another
                        # call to _on_user_input_transcribed with ev.is_final=True and more text.
                        # So we just continue waiting until timeout or a final event triggers action.
                        # Break only on timeout to let final handler handle things.
                        # (This loop is primarily to limit blocking time.)
                        # Continue waiting...
                        pass

                    # timeout expired with no decisive information -> do nothing now
                    logger.debug("bg-validate timed out for interim: %r", text)
                    return

                # FINAL event processing (ev.is_final True)
                # Re-evaluate using final tokens: interrupt has priority
                if self._contains_interrupt_word(tokens):
                    logger.info("🛑 (final) detected interrupt word in: %r", text)
                    try:
                        self._session.interrupt(force=True)
                    except Exception as e:
                        logger.exception("interrupt failed (final): %s", e)
                    return

                # If final is pure ack AND agent was speaking at the time of the user's audio,
                # clear the user turn so agent continues (this is safe on final).
                if self._is_only_acknowledgement(tokens) and self._is_agent_speaking():
                    logger.info("✓ (final) pure ack detected while speaking: %r → continue", text)
                    try:
                        self._session.clear_user_turn()
                    except Exception:
                        logger.exception("clear_user_turn failed (final)")
                    return

                # Otherwise it's meaningful content — stop agent (if speaking)
                if self._is_agent_speaking():
                    logger.info("💬 (final) user provided real input while speaking: %r → interrupt", text)
                    try:
                        self._session.interrupt(force=True)
                    except Exception as e:
                        logger.exception("interrupt failed (final real input): %s", e)
                else:
                    # Agent silent; this is a normal user turn -> do nothing here
                    logger.debug("User final transcript while agent silent: %r", text)

            except asyncio.CancelledError:
                logger.debug("Background validation cancelled for text: %r", text)
                raise
            except Exception:
                logger.exception("Unexpected error in background validation for text: %r", text)

    def _on_user_input_transcribed_sync(self, ev: UserInputTranscribedEvent) -> None:
        """
        Sync wrapper called by the session event loop. It schedules the async
        background handler which performs the real decision-making.
        """
        # Pull transcript (fast)
        text = (ev.transcript or "").strip()
        if not text:
            return

        tokens = self._tokenize(text)
        if not tokens:
            return

        # If the agent is not speaking, do nothing here: let the normal processing handle the turn
        if not self._is_agent_speaking():
            logger.debug("User input while agent silent (no backchannel filtering): %r", text)
            return

        # If agent is speaking, schedule/execute background validation immediately.
        # The background validator will attempt fast interim decisions and also handle final events.
        try:
            self._schedule_bg_validation(text, tokens, ev)
        except Exception:
            logger.exception("Failed to schedule background validation")

    def _on_user_input_transcribed(self, ev: UserInputTranscribedEvent) -> None:
        """
        Event hook called by the session. It must be synchronous (session event loop),
        so we call the sync wrapper which schedules the asynchronous worker.
        """
        # We are not `await`ing anything here; scheduling is enough.
        try:
            self._on_user_input_transcribed_sync(ev)
        except Exception:
            logger.exception("Error in user_input_transcribed handler")

# SERVER SETUP 
class KellyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Keep your responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or other special characters in your responses. "
                "You are curious and friendly, and have a sense of humor. "
                "You will speak English to the user."
            ),
        )


server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    # Load VAD into proc.userdata for reuse
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        allow_interruptions=True,
        # Extremely high threshold in original; you can tune these values as needed.
        min_interruption_duration=3.0,
        min_interruption_words=0,
        vad=ctx.proc.userdata["vad"],
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=0.8,
    )

    # Attach the backchannel filter (improved)
    BackchannelFilter(session).attach()

    # Start the session normally
    await session.start(
        agent=KellyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
