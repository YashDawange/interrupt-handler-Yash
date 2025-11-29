import logging
import re
import asyncio
from typing import Set, Optional
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
    UserInputTranscribedEvent,
    AgentStateChangedEvent,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("basic-agent")
load_dotenv()

# Configurable ignore words list (backchanneling/fillers)
IGNORE_WORDS: Set[str] = {
    "yeah", "yes", "yep", "yup", "ya",
    "ok", "okay", "okey", "k",
    "hmm", "hmmm", "mm", "mmm", "mhm", "mmhm",
    "uh", "um", "uhm", "uh-huh", "mm-hmm",
    "right", "sure", "gotcha", "got it",
    "alright", "cool", "nice"
}

# Command words that should always interrupt
COMMAND_WORDS: Set[str] = {
    "stop", "wait", "hold", "no", "pause", "cancel", "interrupt", "hold on"
}


def normalize_text(text: str) -> str:
    """Remove punctuation and normalize text for comparison."""
    return re.sub(r'[^\w\s]', '', text.lower()).strip()


def is_only_filler(transcript: str) -> bool:
    """Check if transcript contains only filler words."""
    normalized = normalize_text(transcript)
    words = normalized.split()
    
    if not words:
        return True
    
    # Check if ALL words are fillers
    is_filler = all(word in IGNORE_WORDS for word in words)
    logger.debug(f"Filler check: '{transcript}' -> words={words}, is_filler={is_filler}")
    return is_filler


def contains_command(transcript: str) -> bool:
    """Check if transcript contains any command words."""
    normalized = normalize_text(transcript)
    words = normalized.split()
    
    has_command = any(word in COMMAND_WORDS for word in words)
    logger.debug(f"Command check: '{transcript}' -> words={words}, has_command={has_command}")
    return has_command


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice."
            "with that in mind keep your responses concise and to the point."
            "do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "you will speak english to the user",
        )
        self.is_agent_speaking = False
        self.session_ref: Optional[AgentSession] = None

    async def on_enter(self):
        # Store session reference for access to methods
        self.session_ref = self.session
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

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
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),    # ignore very short bursts of sound (<400ms)),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        # These settings help handle false interruptions
        resume_false_interruption=True,
        false_interruption_timeout=0.15,  # Wait 2.5s for STT before giving up
        min_interruption_words=1,  # Require at least 2 words to interrupt
    )

    agent_instance = MyAgent()
    
    # Track agent speaking state
    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: AgentStateChangedEvent):
        agent_instance.is_agent_speaking = (ev.new_state == "speaking")
        logger.info(f"Agent state: {ev.new_state}, is_speaking: {agent_instance.is_agent_speaking}")

    # Intercept and filter transcriptions based on context
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent):
        transcript = ev.transcript.strip()
        normalized = normalize_text(transcript)
        logger.info(f"📝 Transcribed: '{transcript}' | Agent speaking: {agent_instance.is_agent_speaking}")

        # ------------------------------------------------------------
        # 1. Handle PARTIAL transcripts BEFORE interruption occurs
        # ------------------------------------------------------------
        if agent_instance.is_agent_speaking and not ev.is_final:

            # COMMAND words (stop, wait, pause) MUST interrupt
            for cmd in COMMAND_WORDS:
                if normalized.startswith(cmd[:2]):
                    logger.info(f"[Partial command detected] '{transcript}' — ALLOW INTERRUPTION")
                    return

            # FILLER words should NOT interrupt the agent
            for filler in IGNORE_WORDS:
                if normalized.startswith(filler[:2]):
                    logger.info(f"[Partial filler detected] '{transcript}' — BLOCKING INTERRUPTION")
                    session.clear_user_turn()
                    return

            # Unknown partial — allow normal behavior
            return

        # ------------------------------------------------------------
        # 2. Final transcript logic (your original code)
        # ------------------------------------------------------------
        if agent_instance.is_agent_speaking:
            if contains_command(transcript):
                logger.info(f"Command detected: '{transcript}' - ALLOWING INTERRUPTION")
                return

            if is_only_filler(transcript):
                logger.info(f"Filler-only detected: '{transcript}' - IGNORING & CLEARING")
                session.clear_user_turn()
                return

            logger.info(f"✓ Substantive input: '{transcript}' - ALLOWING INTERRUPTION")

        else:
            logger.info(f"✓ Agent silent - accepting input: '{transcript}'")

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
        agent=agent_instance,
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