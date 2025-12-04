import logging
import os
import re
from collections.abc import AsyncIterable

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, room_io
from livekit.agents.llm import function_tool
from livekit.plugins import openai  

logger = logging.getLogger("realtime-with-tts")
logger.setLevel(logging.INFO)

load_dotenv()


def _load_word_list(env_var_name: str, default: list[str]) -> set[str]:
    """
    Helper to load comma-separated word lists from env, with a Python default.
    Example:
      INTERRUPT_IGNORE_WORDS="yeah,ok,hmm"
    """
    raw = os.getenv(env_var_name)
    if not raw:
        return {w.strip().lower() for w in default if w.strip()}
    return {w.strip().lower() for w in raw.split(",") if w.strip()}


def _normalize_tokens(text: str) -> list[str]:
    """
    Lowercase, strip punctuation, split into tokens.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [tok for tok in text.split() if tok]


def _extract_text_from_speech_event(event) -> str | None:
    """
    Try to pull plain text out of whatever the STT node yields.

    This is written to be robust to different STT event shapes:
    - plain `str`
    - object with `.text`
    - object with `.alternatives[0].text`
    """
    if isinstance(event, str):
        return event

    # Common pattern: event.text
    text = getattr(event, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    # Some STT APIs expose alternatives: event.alternatives[0].text
    alts = getattr(event, "alternatives", None)
    if alts and hasattr(alts[0], "text"):
        alt_text = alts[0].text
        if isinstance(alt_text, str) and alt_text.strip():
            return alt_text

    return None


class WeatherAgent(Agent):
    def __init__(self) -> None:
        # Words that should NOT interrupt when we are speaking
        ignore_default = ["yeah", "ok", "okay", "hmm", "right", "uh-huh", "uh huh", "mm", "uh"]
        # Words/phrases that SHOULD interrupt even if mixed with ignore words
        command_default = ["stop", "wait", "no", "hold on", "hang on", "pause"]

        self._ignore_words = _load_word_list("INTERRUPT_IGNORE_WORDS", ignore_default)
        self._command_words = _load_word_list("INTERRUPT_COMMAND_WORDS", command_default)

        # Tracks whether this agent is currently outputting TTS audio
        self._is_speaking: bool = False

        super().__init__(
            instructions="You are a helpful assistant.",
            # Realtime LLM for reasoning
            llm=openai.realtime.RealtimeModel(modalities=["text"]),
            # Separate TTS for audio output
            tts=openai.TTS(voice="ash"),
            # We keep default `allow_interruptions=True` (session-level) and
            # implement our own semantic filtering in stt_node.
        )

    @function_tool
    async def get_weather(self, location: str):
        """Called when the user asks about the weather.

        Args:
            location: The location to get the weather for
        """

        logger.info(f"getting weather for {location}")
        return f"The weather in {location} is sunny, and the temperature is 20 degrees Celsius."


    async def tts_node(
        self, text: AsyncIterable[str], model_settings
    ) -> AsyncIterable:
        """
        Wrap the default TTS node so we know exactly when the agent
        is speaking vs. silent.

        - When this generator is active -> _is_speaking = True
        - When it completes / errors -> _is_speaking = False
        """
        self._is_speaking = True
        logger.debug("TTS started; marking agent as speaking.")
        try:
            async for frame in Agent.default.tts_node(self, text, model_settings):
                # We don't modify the audio; just pass it through.
                yield frame
        finally:
            self._is_speaking = False
            logger.debug("TTS finished; marking agent as silent.")

    async def stt_node(
        self, audio: AsyncIterable, model_settings
    ) -> AsyncIterable:
        """
        Wrap the default STT node to implement interrupt filtering:

        - When the agent is SPEAKING:
            - If input is ONLY ignore words ("yeah", "ok", "hmm"), we swallow it.
            - If input contains any command words ("stop", "wait", "no"), we let it through
              so the normal interruption logic can fire.
            - If input has other content, we let it through as normal.

        - When the agent is SILENT:
            - We do not filter anything; "yeah" is treated as valid input.
        """
        async for event in Agent.default.stt_node(self, audio, model_settings):
            text = _extract_text_from_speech_event(event)

            # If we cannot parse text from the event, just pass it through.
            if not text:
                yield event
                continue

            tokens = _normalize_tokens(text)
            if not tokens:
                yield event
                continue

            has_command = any(tok in self._command_words for tok in tokens)
            all_ignore = tokens and all(tok in self._ignore_words for tok in tokens)

            if not self._is_speaking:
                # Agent is silent -> treat everything as normal input.
                # So "yeah" here becomes a valid answer.
                logger.debug(
                    "Agent silent; passing STT text through: %s", text
                )
                yield event
                continue

            # Agent IS speaking from here on.

            if has_command:
                # Mixed or pure command ("stop", "no stop", "yeah wait a sec")
                # We let this pass so the built in interruption pipeline
                # can cut TTS and start a new turn.
                logger.info(
                    "Agent speaking; received COMMAND text -> allowing interrupt: %s",
                    text,
                )
                yield event
            elif all_ignore:
                # Pure backchannel while agent is speaking: ignore completely.
                logger.info(
                    "Agent speaking; ignoring backchannel STT text: %s", text
                )
                # Swallow the event implies no interruption, no hiccup.
                continue
            else:
                # Some other normal text while agent is speaking ("actually I meant...")
                # Let it through: the agent SHOULD be interruptible here.
                logger.info(
                    "Agent speaking; passing meaningful STT text through: %s",
                    text,
                )
                yield event


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession()

    await session.start(
        agent=WeatherAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            text_output=True,
            audio_output=True,  
        ),
    )
    # Optional: greet the user once connected
    session.generate_reply(instructions="say hello to the user in English")


if __name__ == "__main__":
    cli.run_app(server)