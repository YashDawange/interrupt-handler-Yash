import logging
import os
import re

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    UserInputTranscribedEvent,
    AgentStateChangedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
# from livekit.plugins import noise_cancellation  # optional

logger = logging.getLogger("basic-agent")
load_dotenv()

# ===========
# CONFIGURABLE BACKCHANNEL / COMMAND LISTS
# ===========

# You can override these via env vars:
#   BACKCHANNEL_WORDS="yeah, ok, okay, hmm, uh-huh"
#   INTERRUPT_WORDS="stop, wait, no, cancel"
_DEFAULT_BACKCHANNEL_WORDS = {
    # Short Fillers & Continuers
    "ah", "aha", "hm", "hmm", "mhm", "mhmm",
    "mm-hmm", "mmhmm", "uh-huh", "um", "uh", "uhhuh",

    # Affirmations & Agreement
    "absolutely", "exactly", "indeed", "right", "sure",
    "true", "understood", "correct", "definitely",

    # Casual Acknowledgments
    "alright", "cool", "fine", "nice", "ok", "okay",
    "yeah", "yep", "yes", "yup", "sounds good",

    # Phrases & Feedback
    "go on", "got it", "i see", "makes sense",
    "keep going", "tell me more",

    # Reactions
    "really", "wow", "for real", "seriously",
    "interesting", "no way",
}

_DEFAULT_INTERRUPT_WORDS = {
    "stop",
    "wait",
    "no",
    "hold",
    "cancel",
    "pause",
    "enough",
    "hold on",
}

def _parse_word_list(env_name: str, default: set[str]) -> set[str]:
    raw = os.getenv(env_name)
    if not raw:
        return default
    return {w.strip().lower() for w in raw.split(",") if w.strip()}

BACKCHANNEL_WORDS = _parse_word_list("BACKCHANNEL_WORDS", _DEFAULT_BACKCHANNEL_WORDS)
INTERRUPT_WORDS = _parse_word_list("INTERRUPT_WORDS", _DEFAULT_INTERRUPT_WORDS)


def _normalize_tokens(text: str) -> list[str]:
    # split on non-word characters, lowercased
    return [t for t in re.split(r"\W+", text.lower()) if t]


def is_soft_backchannel(text: str) -> bool:
    """
    Returns True if the utterance is ONLY made of backchannel words
    like 'yeah', 'ok', 'hmm', etc.
    """
    tokens = _normalize_tokens(text)
    if not tokens:
        return False
    return all(tok in BACKCHANNEL_WORDS for tok in tokens)


def contains_strong_interrupt(text: str) -> bool:
    """
    Returns True if the utterance contains any strong interrupt word
    like 'stop', 'wait', 'no', 'cancel', etc.
    """
    tokens = _normalize_tokens(text)
    return any(tok in INTERRUPT_WORDS for tok in tokens)


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. "
                "You are a full conversational AI assistant and can freely discuss, explain, "
                "and reason about any topic the user asks. "
                "You are NOT limited to any single domain. "
                "You should only use tools when they are clearly useful, "
                "and you should never say that you are incapable of answering general questions. "
                "If a question is abstract or conceptual, explain it in simple terms. "
                "If the user asks about weather, you may use the weather tool. "
                "Keep responses concise, natural, and conversational. "
                "Do not use emojis, markdown, or special formatting. "
                "Speak in English."
            ),
        )

    async def on_enter(self):
        # When the agent is added to the session, it'll generate a reply
        # according to its instructions.
        # IMPORTANT: we rely on AgentSession options for interruption behavior.
        self.session.generate_reply()

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(
        self,
        context: RunContext,
        location: str,
        latitude: str,
        longitude: str,
    ):
        """
        OPTIONAL helper tool.

        Use this tool ONLY when the user explicitly asks for weather information
        (e.g., temperature, forecast, rain, humidity).
        Do NOT use this tool for general conversation or explanations.
        """
        logger.info(f"Weather tool invoked for location: {location}")
        return "It is currently sunny with a temperature of 70 degrees."

server = AgentServer()


def prewarm(proc: JobProcess):
    # Load VAD once per worker process
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # ===========
    # AGENT SESSION SETUP WITH CUSTOM INTERRUPTION HANDLING
    # ===========
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="google/gemini-2.5-flash",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",

        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],

        preemptive_generation=True,

        # 🚫 Disable automatic interruptions from the framework.
        allow_interruptions=True,

        # ✅ Still send user audio to STT even if we can't auto-interrupt.
        discard_audio_if_uninterruptible=True,
        
        min_interruption_duration=0.6,   # seconds
        min_interruption_words=2,
    )



    # ===========
    # METRICS LOGGING (existing code)
    # ===========
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # ===========
    # INTELLIGENT INTERRUPTION LAYER
    # ===========

    # Track whether the agent is currently speaking
    agent_is_speaking = {"value": False}

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        # States: initializing, listening, thinking, speaking
        agent_is_speaking["value"] = ev.new_state == "speaking"
        logger.debug("Agent state changed: %s -> %s", ev.old_state, ev.new_state)

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        """
        Core logic:

        - If the agent is NOT speaking → do nothing, let normal behavior happen.
          This makes 'Yeah.' a valid answer when the agent is silent.

        - If the agent IS speaking:
            * If final transcript is only backchannel words → ignore.
            * If final transcript contains any interrupt word (or any non-backchannel word) → interrupt.
        """
        text = (ev.transcript or "").strip()
        if not text:
            return

        if not agent_is_speaking["value"]:
            # Agent is idle/listening/thinking → treat normally (Scenario 2).
            logger.debug(
                "User speaking while agent not speaking: %r (final=%s)",
                text,
                ev.is_final,
            )
            return

        # We're only interested in final STT segments to avoid jitter
        if not ev.is_final:
            logger.debug("Interim transcript while speaking (ignored for logic): %r", text)
            return

        logger.info("User spoke while agent is speaking: %r", text)

        if is_soft_backchannel(text):
            # Scenario 1: backchannel while agent is talking → ignore completely.
            logger.info("Ignoring soft backchannel while agent is speaking: %r", text)
            # Clear the current user turn so these words are not later committed.
            session.clear_user_turn()
            return

        if contains_strong_interrupt(text):
            # Scenario 3 and 4: explicit interruption while agent is talking.
            logger.info(
                "Detected strong interrupt while agent speaking. Interrupting: %r", text
            )
            session.interrupt(force=True)
            return

        # If it’s not pure backchannel and not clearly in INTERRUPT_WORDS, we treat
        # it as an interruption as well (mixed sentence, or arbitrary command).
        # This satisfies: "Yeah okay but wait" → interrupt.
        logger.info(
            "Detected mixed/non-soft input while speaking. Interrupting: %r", text
        )
        session.interrupt(force=True)

    # ===========
    # START SESSION
    # ===========
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # noise_cancellation=noise_cancellation.BVC(),  # optional
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
