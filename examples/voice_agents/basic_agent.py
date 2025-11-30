import logging
import re
import asyncio
from typing import Set, Optional, AsyncIterator
from dataclasses import dataclass, field
import time

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
)
from livekit.agents.llm import function_tool
from livekit.agents.vad import VADEvent, VADEventType
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("smart-interrupt-agent")

load_dotenv()

# ============================================================================
# CONFIGURABLE WORD LISTS (Easy to modify via config/env vars)
# ============================================================================

BACKCHANNEL_WORDS: Set[str] = {
    "yeah", "yes", "yep", "yup", "ya",
    "ok", "okay", "k", "kay",
    "hmm", "hm", "mhm", "mm", "mmm", "uh-huh", "uh huh", "uhuh",
    "right", "alright", "sure",
    "aha", "ah", "oh", "uh",
    "got it", "gotcha",
    "i see", "cool", "nice", "great", "good",
}

INTERRUPT_WORDS: Set[str] = {
    "stop", "wait", "hold on", "pause", "hold",
    "no", "nope", "actually", "but",
    "hang on", "one second", "just a moment",
    "excuse me", "sorry", "question",
    "hey", "listen",
}


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    return text


def is_only_backchannel(transcript: str) -> bool:
    normalized = normalize_text(transcript)
    words = normalized.split()
    if not words:
        return True
    return all(word in BACKCHANNEL_WORDS for word in words)


def contains_interrupt_word(transcript: str) -> bool:
    normalized = normalize_text(transcript)
    for phrase in INTERRUPT_WORDS:
        if phrase in normalized:
            return True
    words = normalized.split()
    return any(word in INTERRUPT_WORDS for word in words)


# ============================================================================
# SMART VAD WRAPPER - THE KEY TO ZERO-PAUSE BACKCHANNELING
# This wraps the VAD stream and suppresses events during backchannel detection
# ============================================================================

@dataclass
class SpeechBuffer:
    """Buffers speech events until we can determine if it's backchannel or real interrupt."""
    start_event: Optional[VADEvent] = None
    end_event: Optional[VADEvent] = None
    start_time: float = 0.0
    transcript: str = ""
    is_validated: bool = False
    should_emit: bool = True


class SmartVADStream:
    """
    Wraps VAD stream to implement intelligent backchannel filtering.
    
    Strategy:
    - Buffers SPEECH_START events while agent is speaking
    - Waits for STT transcript before deciding to emit or suppress
    - For interrupt words: emit immediately
    - For backchannels: suppress entirely (no state change = no pause)
    """
    
    def __init__(
        self, 
        base_stream: AsyncIterator[VADEvent],
        backchannel_window: float = 1.2,  # Max duration to consider as backchannel
    ):
        self._base_stream = base_stream
        self._backchannel_window = backchannel_window
        self._agent_speaking = False
        self._current_buffer: Optional[SpeechBuffer] = None
        self._pending_events: asyncio.Queue = asyncio.Queue()
        self._transcript_queue: asyncio.Queue = asyncio.Queue()
        self._should_stop = False
        
    def set_agent_speaking(self, speaking: bool):
        self._agent_speaking = speaking
        logger.debug(f"SmartVAD: agent_speaking = {speaking}")
        if not speaking:
            # Agent stopped speaking, flush any buffered events
            self._flush_buffer(emit=True)
    
    def on_transcript(self, transcript: str, is_final: bool):
        """Feed STT transcripts for validation."""
        if self._current_buffer and self._agent_speaking:
            self._current_buffer.transcript = transcript
            
            # Check for immediate interrupt words
            if contains_interrupt_word(transcript):
                logger.info(f"SmartVAD: Interrupt word detected: '{transcript}' - EMITTING")
                self._current_buffer.should_emit = True
                self._current_buffer.is_validated = True
                self._flush_buffer(emit=True)
                return
            
            # Check for backchannel on final transcript
            if is_final:
                if is_only_backchannel(transcript):
                    logger.info(f"SmartVAD: Backchannel suppressed: '{transcript}' - NO PAUSE")
                    self._current_buffer.should_emit = False
                    self._current_buffer.is_validated = True
                    self._flush_buffer(emit=False)
                else:
                    # Real speech, emit the events
                    logger.info(f"SmartVAD: Real speech detected: '{transcript}' - EMITTING")
                    self._current_buffer.should_emit = True
                    self._current_buffer.is_validated = True
                    self._flush_buffer(emit=True)
    
    def _flush_buffer(self, emit: bool):
        """Flush buffered events - either emit them or discard."""
        if self._current_buffer:
            if emit and self._current_buffer.start_event:
                self._pending_events.put_nowait(self._current_buffer.start_event)
                if self._current_buffer.end_event:
                    self._pending_events.put_nowait(self._current_buffer.end_event)
            self._current_buffer = None
    
    async def __anext__(self) -> VADEvent:
        while True:
            # First check for any pending events to emit
            try:
                event = self._pending_events.get_nowait()
                return event
            except asyncio.QueueEmpty:
                pass
            
            # Get next event from base stream
            try:
                event = await self._base_stream.__anext__()
            except StopAsyncIteration:
                raise
            
            # If not speaking, pass through all events
            if not self._agent_speaking:
                return event
            
            # Agent is speaking - apply filtering logic
            if event.type == VADEventType.START_OF_SPEECH:
                # Buffer the start event, don't emit yet
                self._current_buffer = SpeechBuffer(
                    start_event=event,
                    start_time=time.time(),
                )
                logger.debug("SmartVAD: Buffering START_OF_SPEECH")
                continue  # Don't emit, wait for transcript
                
            elif event.type == VADEventType.END_OF_SPEECH:
                if self._current_buffer:
                    self._current_buffer.end_event = event
                    
                    # Check if speech was too long to be backchannel
                    duration = time.time() - self._current_buffer.start_time
                    if duration > self._backchannel_window:
                        # Too long for backchannel, emit
                        logger.debug(f"SmartVAD: Speech too long ({duration:.2f}s), emitting")
                        self._flush_buffer(emit=True)
                    elif not self._current_buffer.is_validated:
                        # Wait a bit more for transcript
                        await asyncio.sleep(0.1)
                        if not self._current_buffer.is_validated:
                            # Timeout, emit to be safe
                            logger.debug("SmartVAD: Validation timeout, emitting")
                            self._flush_buffer(emit=True)
                continue  # Don't emit END directly, handled by flush
            
            else:
                # Other event types, pass through
                return event
    
    def __aiter__(self):
        return self


class SmartVAD:
    """
    Wrapper around Silero VAD that provides intelligent backchannel filtering.
    """
    
    def __init__(self, base_vad):
        self._base_vad = base_vad
        self._current_stream: Optional[SmartVADStream] = None
        
    def set_agent_speaking(self, speaking: bool):
        if self._current_stream:
            self._current_stream.set_agent_speaking(speaking)
    
    def on_transcript(self, transcript: str, is_final: bool):
        if self._current_stream:
            self._current_stream.on_transcript(transcript, is_final)
    
    def stream(self, *args, **kwargs) -> SmartVADStream:
        base_stream = self._base_vad.stream(*args, **kwargs)
        self._current_stream = SmartVADStream(base_stream)
        return self._current_stream
    
    # Delegate all other attributes to base VAD
    def __getattr__(self, name):
        return getattr(self._base_vad, name)


# ============================================================================
# SMART TURN DETECTOR (Backup filtering at turn level)
# ============================================================================

class SmartTurnDetector(MultilingualModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._agent_speaking = False
    
    def set_agent_speaking(self, speaking: bool):
        self._agent_speaking = speaking
    
    async def predict_end_of_turn(self, chat_ctx, timeout: float = 1.0):
        last_user_text = ""
        for msg in reversed(chat_ctx.items):
            if hasattr(msg, 'role') and msg.role == "user":
                if hasattr(msg, 'content'):
                    last_user_text = str(msg.content) if msg.content else ""
                break
        
        if self._agent_speaking:
            if is_only_backchannel(last_user_text):
                logger.info(f"TurnDetector: Filtering backchannel: '{last_user_text}'")
                return 0.0
            if contains_interrupt_word(last_user_text):
                logger.info(f"TurnDetector: Interrupt word: '{last_user_text}'")
                return 1.0
        
        return await super().predict_end_of_turn(chat_ctx, timeout=timeout)


# ============================================================================
# AGENT
# ============================================================================

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""Your name is Kelly. You would interact with users via voice.
            With that in mind keep your responses concise and to the point.
            Do not use emojis, asterisks, markdown, or other special characters in your responses.
            You are curious and friendly, and have a sense of humor.
            You will speak english to the user.
            When giving explanations, feel free to give detailed responses.
            If a user says acknowledgement words like 'yeah' or 'ok' after you ask a question,
            treat it as confirmation and proceed accordingly.""",
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information."""
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."

    @function_tool
    async def tell_long_story(self, context: RunContext):
        """Called when the user asks for a story or long explanation."""
        return """Here's a detailed story: Once upon a time, in a land far far away, 
        there lived a wise old wizard who spent his days studying ancient scrolls. 
        He discovered many secrets about the universe, including how stars are born 
        and why the ocean has tides. His knowledge was sought by kings and peasants alike.
        The wizard traveled to many kingdoms sharing his wisdom. He taught princes about 
        leadership, helped farmers understand the weather, and showed children the wonders 
        of the natural world. His greatest lesson was that true wisdom comes from listening 
        carefully and treating everyone with kindness and respect. The wizard's journey 
        continued for many years, and his legacy lived on through all those he helped."""


server = AgentServer()


def prewarm(proc: JobProcess):
    # Load base VAD
    base_vad = silero.VAD.load()
    # Wrap it with our smart filtering
    proc.userdata["smart_vad"] = SmartVAD(base_vad)


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    
    # Get our smart VAD wrapper
    smart_vad = ctx.proc.userdata["smart_vad"]
    
    # Create turn detector
    turn_detector = SmartTurnDetector()
    
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=turn_detector,
        vad=smart_vad,
        # Keep interruptions enabled for real interrupts
        allow_interruptions=True,
        # These are now backup - main filtering is in SmartVAD
        min_interruption_duration=0.3,
        resume_false_interruption=True,
        false_interruption_timeout=0.5,
        preemptive_generation=True,
    )
    
    # Sync agent speaking state with our filters
    @session.on("agent_state_changed")
    def on_state_changed(ev):
        is_speaking = (ev.new_state == "speaking")
        smart_vad.set_agent_speaking(is_speaking)
        turn_detector.set_agent_speaking(is_speaking)
        logger.info(f"Agent state: {ev.old_state} -> {ev.new_state}")
    
    # Feed transcripts to SmartVAD for validation
    @session.on("user_input_transcribed")
    def on_transcript(ev):
        transcript = ev.transcript.strip() if ev.transcript else ""
        if transcript:
            smart_vad.on_transcript(transcript, ev.is_final)
            logger.debug(f"Transcript: '{transcript}' (final={ev.is_final})")
    
    # Metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
