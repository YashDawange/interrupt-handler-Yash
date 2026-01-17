import logging
import asyncio
import re
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


class SmartInterruptionGuard:
    """
    STT-based interruption handler that completely bypasses VAD for interruption decisions.
    
    Strategy:
    1. Disable VAD-based interruptions completely when agent is speaking
    2. Analyze STT transcripts (partial and final) in real-time
    3. Only allow agent interruption when detecting:
       - Explicit interrupt words (wait, stop, etc.)
       - Substantive questions or statements
    4. Block interruption for passive acknowledgments (yeah, ok, hmm)
    """
    
    def __init__(self, ignore_words: list = None, interrupt_words: list = None):
        self.ignore_words: Set[str] = set(w.lower() for w in (ignore_words or IGNORE_WORDS))
        self.interrupt_words: Set[str] = set(w.lower() for w in (interrupt_words or INTERRUPT_WORDS))
        
        self.agent_state = AgentState.IDLE
        self.current_transcript = ""
        self.should_interrupt = False
        
        # Stats
        self.stats = {
            'blocked_passive': 0,
            'allowed_interrupts': 0,
            'total_transcripts': 0,
        }
    
    def set_state(self, state: AgentState):
        """Update agent state"""
        self.agent_state = state
        logger.info(f"🔄 Agent state: {state.value}")
    
    def _normalize(self, text: str) -> str:
        """Normalize text for analysis"""
        # Remove punctuation, lowercase, strip
        return re.sub(r'[^\w\s]', '', text.lower().strip())
    
    def _get_words(self, text: str) -> list:
        """Extract words from text"""
        normalized = self._normalize(text)
        return [w for w in normalized.split() if w]
    
    def _has_interrupt_word(self, text: str) -> bool:
        """Check if text contains any interrupt word"""
        normalized = self._normalize(text)
        for interrupt_word in self.interrupt_words:
            # Check for whole word match
            if re.search(r'\b' + re.escape(interrupt_word) + r'\b', normalized):
                return True
        return False
    
    def _is_only_passive(self, text: str) -> bool:
        """Check if text contains ONLY passive acknowledgment words"""
        words = self._get_words(text)
        if not words:
            return True
        
        # All words must be in ignore list
        return all(word in self.ignore_words for word in words)
    
    def _is_substantive(self, text: str) -> bool:
        """Check if text has substantive content (not just passive acknowledgment)"""
        words = self._get_words(text)
        if not words:
            return False
        
        # Has at least one word that's NOT in the ignore list
        non_passive_words = [w for w in words if w not in self.ignore_words]
        return len(non_passive_words) > 0
    
    def analyze_transcript(self, text: str, is_final: bool = False) -> bool:
        """
        Analyze transcript and decide if agent should be interrupted.
        
        Returns:
            True = interrupt the agent (stop speaking)
            False = do NOT interrupt (continue speaking)
        """
        if not text or not text.strip():
            return False
        
        self.stats['total_transcripts'] += 1
        self.current_transcript = text
        
        transcript_type = "FINAL" if is_final else "PARTIAL"
        logger.debug(f"📝 {transcript_type}: '{text}'")
        
        # When agent is NOT speaking, all input is valid
        if self.agent_state != AgentState.SPEAKING:
            logger.debug(f"   → Agent idle, input is valid")
            return True
        
        # Agent IS speaking - apply filtering logic
        
        # Priority 1: Explicit interrupt words ALWAYS interrupt
        if self._has_interrupt_word(text):
            logger.info(f"✓ INTERRUPT - has interrupt word: '{text}'")
            self.stats['allowed_interrupts'] += 1
            return True
        
        # Priority 2: Only passive acknowledgment - BLOCK
        if self._is_only_passive(text):
            logger.info(f"✗ CONTINUE - only passive words: '{text}'")
            self.stats['blocked_passive'] += 1
            return False
        
        # Priority 3: Has substantive content - INTERRUPT
        if self._is_substantive(text):
            logger.info(f"✓ INTERRUPT - substantive content: '{text}'")
            self.stats['allowed_interrupts'] += 1
            return True
        
        # Default: continue speaking (don't interrupt on unclear input)
        logger.info(f"✗ CONTINUE - default (unclear): '{text}'")
        self.stats['blocked_passive'] += 1
        return False
    
    def reset_transcript(self):
        """Reset current transcript tracking"""
        self.current_transcript = ""
        self.should_interrupt = False


class MyAgent(Agent):
    def __init__(self, guard: SmartInterruptionGuard) -> None:
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
                "mean they are listening - continue speaking naturally. "
                "Only stop if they say words like 'wait', 'stop', 'no', or ask a real question."
            )
        )
        self.guard = guard
        
    async def on_enter(self):
        self.guard.set_state(AgentState.IDLE)
        # Allow interruptions when idle (to receive initial input)
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
    
    guard = SmartInterruptionGuard(
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
        # CRITICAL: These settings control how false interruptions are handled
        resume_false_interruption=True,  # Resume if interruption was false
        false_interruption_timeout=0.5,   # Wait 500ms for STT before deciding
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
    
    # Flag to track if we're processing an interruption
    processing_interruption = False
    
    @session.on("agent_started_speaking")
    def _on_agent_started_speaking():
        """Agent has started speaking"""
        guard.set_state(AgentState.SPEAKING)
        guard.reset_transcript()
        # CRITICAL: Disable VAD-based interruptions when agent starts speaking
        # We will ONLY interrupt based on STT analysis
        agent.allow_interruptions = False
        logger.info("🗣️  AGENT SPEAKING - VAD interruptions DISABLED")
    
    @session.on("agent_stopped_speaking")
    def _on_agent_stopped_speaking():
        """Agent has stopped speaking"""
        guard.set_state(AgentState.IDLE)
        guard.reset_transcript()
        # Enable interruptions when agent is idle (to receive user input)
        agent.allow_interruptions = True
        logger.info("🤐 AGENT STOPPED - interruptions ENABLED")
    
    @session.on("user_started_speaking")
    def _on_user_started_speaking():
        """User has started speaking (VAD detected)"""
        logger.info("🎤 USER STARTED SPEAKING (VAD detected)")
        # Don't change allow_interruptions here
        # Wait for STT transcript to make decision
    
    @session.on("user_transcript_updated")
    def _on_user_transcript_updated(transcript):
        """
        CRITICAL HANDLER: Partial/interim transcriptions.
        This is where we analyze transcripts in real-time and decide
        whether to interrupt the agent.
        """
        if not hasattr(transcript, 'text'):
            return
        
        partial_text = transcript.text
        if not partial_text or not partial_text.strip():
            return
        
        # Analyze the partial transcript
        should_interrupt = guard.analyze_transcript(partial_text, is_final=False)
        
        # Update agent's interruption setting based on analysis
        if guard.agent_state == AgentState.SPEAKING:
            # Only allow interruption if transcript warrants it
            agent.allow_interruptions = should_interrupt
            
            if should_interrupt:
                logger.debug(f"   ⚡ Enabling interruption for: '{partial_text}'")
            else:
                logger.debug(f"   🛡️  Blocking interruption for: '{partial_text}'")
    
    @session.on("user_speech_committed")
    def _on_user_speech_committed(message):
        """
        Final transcription received.
        Make final decision on whether this should interrupt.
        """
        text = message.text if hasattr(message, 'text') else str(message)
        
        if not text or not text.strip():
            # Empty final transcript - reset to safe state
            if guard.agent_state == AgentState.IDLE:
                agent.allow_interruptions = True
            else:
                agent.allow_interruptions = False
            return
        
        logger.info(f"📋 FINAL: '{text}'")
        
        # Analyze final transcript
        should_interrupt = guard.analyze_transcript(text, is_final=True)
        
        if guard.agent_state == AgentState.SPEAKING:
            # Set final interruption decision
            agent.allow_interruptions = should_interrupt
            
            if should_interrupt:
                logger.info(f"   ⚡ INTERRUPTING agent for: '{text}'")
            else:
                logger.info(f"   ✅ Agent CONTINUES speaking (ignored: '{text}')")
        else:
            # Agent is idle - this is normal input
            agent.allow_interruptions = True
            logger.info(f"   💬 Processing user input: '{text}'")
    
    @session.on("user_stopped_speaking")
    def _on_user_stopped_speaking():
        """User stopped speaking"""
        logger.info("🎤 USER STOPPED SPEAKING")
        
        # If agent is idle, keep interruptions enabled
        if guard.agent_state == AgentState.IDLE:
            agent.allow_interruptions = True
        # If agent is speaking and we didn't detect valid interruption,
        # keep interruptions disabled
        else:
            # Keep current state - let the transcript analysis decide
            pass
    
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)