import logging
import asyncio
from typing import Set, Optional
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
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

try:
    from config import IGNORE_WORDS, INTERRUPT_WORDS, VERBOSE_LOGGING
except ImportError:
    IGNORE_WORDS = ['yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'right', 'aha', 'mhm', 'mm-hmm', 'sure', 'yep', 'yes', 'got it', 'i see', 'understand', 'alright', 'cool', 'nice']
    INTERRUPT_WORDS = ['wait', 'stop', 'no', 'hold', 'pause', 'hang on', 'hold on', 'one moment', 'actually', 'but', 'however']
    VERBOSE_LOGGING = True

logger = logging.getLogger("intelligent-agent")
if VERBOSE_LOGGING:
    logger.setLevel(logging.INFO)

load_dotenv()


class AgentState(Enum):
    IDLE = "idle"
    SPEAKING = "speaking"


class InterruptionGuard:
    """
    Prevents unwanted interruptions by analyzing PARTIAL transcriptions in real-time
    and dynamically controlling the agent's allow_interruptions property.
    
    Key Strategy (from assignment hint):
    - Use partial STT stream (faster than final transcription)
    - Make decision BEFORE agent stops
    - Control allow_interruptions dynamically
    """
    
    def __init__(self, ignore_words: list = None, interrupt_words: list = None):
        self.ignore_words: Set[str] = set(w.lower() for w in (ignore_words or IGNORE_WORDS))
        self.interrupt_words: Set[str] = set(w.lower() for w in (interrupt_words or INTERRUPT_WORDS))
        
        self.agent_state = AgentState.IDLE
        self.current_partial = ""
        
        self.stats = {
            'blocked_passive': 0,
            'allowed_interrupts': 0,
        }
    
    def set_state(self, state: AgentState):
        """Update agent state"""
        self.agent_state = state
        logger.info(f"🔄 Agent state: {state.value}")
    
    def _normalize(self, text: str) -> str:
        """Normalize text"""
        import re
        return re.sub(r'[^\w\s]', '', text.lower().strip())
    
    def _words(self, text: str) -> list:
        """Get words from text"""
        return [w for w in self._normalize(text).split() if w]
    
    def should_allow_interruption(self, text: str) -> bool:
        """
        CRITICAL FUNCTION: Decide if interruption should be allowed.
        Called on PARTIAL transcriptions to make decision BEFORE agent stops.
        
        Returns:
            True = allow interruption
            False = block interruption (agent continues)
        """
        # If agent not speaking, always allow
        if self.agent_state != AgentState.SPEAKING:
            return True
        
        # Empty text - allow by default
        if not text or not text.strip():
            return True
        
        self.current_partial = text
        norm = self._normalize(text)
        words = self._words(text)
        
        # Priority 1: Check for interrupt words
        for interrupt_word in self.interrupt_words:
            if interrupt_word in norm:
                logger.info(f"✓ ALLOW - has interrupt word '{interrupt_word}': {text}")
                self.stats['allowed_interrupts'] += 1
                return True
        
        # Priority 2: Check if purely passive
        if all(w in self.ignore_words for w in words if w):
            logger.info(f"✗ BLOCK - purely passive: {text}")
            self.stats['blocked_passive'] += 1
            return False
        
        # Priority 3: Has non-passive content
        logger.info(f"✓ ALLOW - non-passive content: {text}")
        self.stats['allowed_interrupts'] += 1
        return True


class MyAgent(Agent):
    def __init__(self, guard: InterruptionGuard) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Keep your responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or other special characters. "
                "You are curious and friendly, and have a sense of humor. "
                "You speak English to the user. "
                "\n\n"
                "When explaining something, speak naturally and completely. "
                "Brief acknowledgments like 'yeah', 'ok', 'hmm' from the user "
                "are automatically filtered - just continue speaking without pause."
            )
        )
        self.guard = guard
        
    async def on_enter(self):
        self.guard.set_state(AgentState.IDLE)
        self.allow_interruptions = True
        self.session.generate_reply()
    
    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        
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
    ctx.log_context_fields = {"room": ctx.room.name}
    
    guard = InterruptionGuard(
        ignore_words=IGNORE_WORDS,
        interrupt_words=INTERRUPT_WORDS
    )
    
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=0,
    )
    
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
        logger.info(f"Interruption Stats: {guard.stats}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Create agent
    agent = MyAgent(guard)
    
    # Track agent speech
    @session.on("agent_started_speaking")
    def _on_agent_started_speaking():
        guard.set_state(AgentState.SPEAKING)
        agent.allow_interruptions = True
        logger.info("🗣️  AGENT SPEAKING")
    
    @session.on("agent_stopped_speaking")
    def _on_agent_stopped_speaking():
        guard.set_state(AgentState.IDLE)
        agent.allow_interruptions = True
        logger.info("🤐 AGENT STOPPED")
    
    # Track user speech
    @session.on("user_started_speaking")
    def _on_user_started_speaking():
        logger.info("🎤 USER SPEAKING")
    
    # CRITICAL: Handle PARTIAL transcriptions (arrive FAST, before final)
    @session.on("user_transcript_updated")
    def _on_user_transcript_updated(transcript):
        """
        KEY HANDLER: This receives PARTIAL/INTERIM transcriptions.
        They arrive FASTER than final transcriptions, giving us time
        to block the interruption BEFORE it happens.
        """
        if not hasattr(transcript, 'text') or not transcript.text:
            return
        
        partial_text = transcript.text
        logger.debug(f"📝 Partial: '{partial_text}'")
        
        # Make decision based on partial text
        should_allow = guard.should_allow_interruption(partial_text)
        
        # Dynamically control interruptions based on content
        if guard.agent_state == AgentState.SPEAKING:
            agent.allow_interruptions = should_allow
            logger.debug(f"   → allow_interruptions = {should_allow}")
    
    # Handle final transcriptions
    @session.on("user_speech_committed")
    def _on_user_speech_committed(message):
        """
        Final transcription (slower). Decision already made via partials.
        """
        text = message.text if hasattr(message, 'text') else str(message)
        
        if text and text.strip():
            logger.info(f"📋 FINAL: '{text}'")
        
        # Reset to allow interruptions
        agent.allow_interruptions = True
    
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)