import logging
import os
import re
from enum import Enum

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

logger = logging.getLogger("basic-agent")
load_dotenv()

class WordCategory(Enum):
    BACKCHANNEL = "backchannel" 
    INTERRUPT = "interrupt"      
    MIXED = "mixed"              
    UNKNOWN = "unknown"           


_DEFAULT_BACKCHANNEL = {
    "ah", "aha", "hm", "hmm", "mhm", "mhmm", "mm-hmm", "mmhmm","uh-huh", "um", "uh", "uhhuh", "oh","yes", "yeah", "yep", "yup", "ok", "okay", "alright","sure", "right", "correct", "exactly", "absolutely","definitely", "indeed", "true", "understood","cool", "nice", "fine", "good", "great","go on", "got it", "i see", "makes sense","keep going", "tell me more", "continue","wow", "really", "interesting", "seriously", "no way",
}

_DEFAULT_INTERRUPT = {
    "stop", "wait", "no", "hold", "cancel", "pause",
    "enough", "hold on", "hang on", "one second",
    "actually", "but", "however", "listen",
}


def _parse_env_words(env_name: str, default: set[str]) -> set[str]:
    raw = os.getenv(env_name)
    if not raw:
        return default
    return {w.strip().lower() for w in raw.split(",") if w.strip()}


BACKCHANNEL_WORDS = _parse_env_words("BACKCHANNEL_WORDS", _DEFAULT_BACKCHANNEL)
INTERRUPT_WORDS = _parse_env_words("INTERRUPT_WORDS", _DEFAULT_INTERRUPT)

logger.info(f"Loaded {len(BACKCHANNEL_WORDS)} backchannel words")
logger.info(f"Loaded {len(INTERRUPT_WORDS)} interrupt words")


def normalize_text(text: str) -> list[str]:
    tokens = re.split(r"\W+", text.lower())
    return [t for t in tokens if t]


def categorize_utterance(text: str) -> WordCategory:
    if not text or not text.strip():
        return WordCategory.UNKNOWN
    
    tokens = normalize_text(text)
    if not tokens:
        return WordCategory.UNKNOWN
    
    if any(token in INTERRUPT_WORDS for token in tokens):
        return WordCategory.INTERRUPT
    
    if all(token in BACKCHANNEL_WORDS for token in tokens):
        return WordCategory.BACKCHANNEL
    
    if any(token in BACKCHANNEL_WORDS for token in tokens):
        return WordCategory.MIXED
    
    return WordCategory.MIXED

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. "
                "You are a friendly, helpful conversational AI assistant. "
                "You can discuss any topic naturally and explain concepts clearly. "
                "Keep responses concise and conversational. "
                "You are NOT limited to any single domain. "
                "You should only use tools when they are clearly useful, "
                "and you should never say that you are incapable of answering general questions. "
                "If a question is abstract or conceptual, explain it in simple terms. "
                "Do not use emojis, markdown formatting, or special characters. "
                "Speak naturally in English."
            ),
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """
        Get current weather information for a location.
        ONLY use this when user explicitly asks about weather.
        
        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """
        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    logger.info("Prewarming VAD model...")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model loaded successfully")


server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    session = AgentSession(
        stt="deepgram/nova-3",              # Speech-to-text
        llm="google/gemini-2.5-flash",      # Language model
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",  # Text-to-speech
        
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        
        preemptive_generation=True,

        allow_interruptions=False,
        
        discard_audio_if_uninterruptible=False,
        
        min_interruption_duration=0.5,
        min_interruption_words=1,
    )
    
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Session usage summary: {summary}")
    
    ctx.add_shutdown_callback(log_usage)

    class AgentState:
        is_speaking: bool = False
        is_thinking: bool = False
    
    state = AgentState()
    
    @session.on("agent_state_changed")
    def on_state_change(ev: AgentStateChangedEvent):
        state.is_speaking = (ev.new_state == "speaking")
        state.is_thinking = (ev.new_state == "thinking")
        
        logger.debug(
            f"Agent state: {ev.old_state} -> {ev.new_state} "
            f"(speaking={state.is_speaking})"
        )
    
    @session.on("user_input_transcribed")
    def on_user_speech(ev: UserInputTranscribedEvent):
        text = (ev.transcript or "").strip()
        
        if not text:
            return

        if not state.is_speaking:
            logger.debug(f"User input while agent silent: '{text}' (final={ev.is_final})")
            return

        if not ev.is_final:
            category = categorize_utterance(text)
            if category == WordCategory.INTERRUPT:
                logger.info(f"INTERRUPT detected (interim): '{text}'")
                session.interrupt(force=True)
            else:
                logger.debug(f"Interim transcript (ignored): '{text}'")
            return
        
        category = categorize_utterance(text)
        
        if category == WordCategory.BACKCHANNEL:
            logger.info(f"Ignoring backchannel: '{text}'")
            session.clear_user_turn()
            
        elif category == WordCategory.INTERRUPT:
            logger.info(f"INTERRUPT command: '{text}'")
            session.interrupt(force=True)
            
        else:  
            logger.info(f"INTERRUPT (mixed/other): '{text}'")
            session.interrupt(force=True)

    logger.info("Starting agent session...")
    
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
