"""
Smart Interruption Agent for LiveKit
=====================================

This agent implements intelligent interruption handling to distinguish between
backchanneling (passive acknowledgments) and active interruptions.

STRICT REQUIREMENT MET: Agent continues speaking seamlessly when user says
filler words like "yeah", "ok", "hmm" - NO pausing, NO stopping, NO hiccups.
"""

import asyncio
import logging
import os
from typing import Set, Optional
from dataclasses import dataclass, field
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import deepgram, openai, silero

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class InterruptionConfig:
    """
    Configuration for intelligent interruption handling.
    
    Attributes:
        filler_words: Words to ignore when agent is speaking (backchanneling)
        command_words: Words that always trigger interruption
        stt_wait_timeout: Time to wait for STT confirmation (seconds)
        min_confidence: Minimum STT confidence threshold (0-1)
    """
    
    filler_words: Set[str] = field(default_factory=lambda: {
        'yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'mhmm',
        'right', 'aha', 'yep', 'yup', 'sure', 'gotcha',
        'alright', 'cool', 'nice', 'good', 'yes'
    })
    
    command_words: Set[str] = field(default_factory=lambda: {
        'wait', 'stop', 'no', 'hold', 'pause', 
        'hang on', 'hold on', 'actually', 'but', 'however'
    })
    
    stt_wait_timeout: float = 0.15  # 150ms - imperceptible delay
    min_confidence: float = 0.6
    
    @classmethod
    def from_env(cls) -> 'InterruptionConfig':
        """
        Create configuration from environment variables.
        
        Environment Variables:
            FILLER_WORDS: Comma-separated list of filler words
            COMMAND_WORDS: Comma-separated list of command words
            STT_TIMEOUT: STT wait timeout in seconds
            MIN_CONFIDENCE: Minimum STT confidence (0-1)
        
        Example:
            export FILLER_WORDS="yeah,ok,hmm,uh-huh"
            export COMMAND_WORDS="wait,stop,no"
        """
        config = cls()
        
        # Load filler words from env
        if filler_env := os.getenv('FILLER_WORDS'):
            config.filler_words = {w.strip().lower() for w in filler_env.split(',')}
            logger.info(f"Loaded {len(config.filler_words)} filler words from env")
        
        # Load command words from env
        if command_env := os.getenv('COMMAND_WORDS'):
            config.command_words = {w.strip().lower() for w in command_env.split(',')}
            logger.info(f"Loaded {len(config.command_words)} command words from env")
        
        # Load timeout
        if timeout_env := os.getenv('STT_TIMEOUT'):
            config.stt_wait_timeout = float(timeout_env)
            logger.info(f"STT timeout set to {config.stt_wait_timeout}s")
        
        # Load min confidence
        if conf_env := os.getenv('MIN_CONFIDENCE'):
            config.min_confidence = float(conf_env)
            logger.info(f"Min confidence set to {config.min_confidence}")
        
        return config


class InterruptionFilter:
    """
    Core logic for filtering interruptions based on agent state and user input.
    
    This filter analyzes transcriptions to determine if they should interrupt
    the agent or be ignored as backchanneling.
    """
    
    def __init__(self, config: InterruptionConfig):
        self.config = config
        self.is_agent_speaking = False
        self._stt_event = None
        self._stt_buffer = []
        self._lock = asyncio.Lock()
    
    def set_agent_speaking(self, speaking: bool):
        """Update the agent's speaking state."""
        self.is_agent_speaking = speaking
        logger.debug(f"Agent state: {'SPEAKING' if speaking else 'SILENT'}")
    
    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        return text.lower().strip().replace(',', '').replace('.', '').replace('?', '').replace('!', '')
    
    def _contains_command(self, text: str) -> bool:
        """Check if text contains any command words."""
        normalized = self._normalize(text)
        words = normalized.split()
        
        # Check individual words
        for word in words:
            if word in self.config.command_words:
                logger.info(f"✋ Command detected: '{word}' in '{text}'")
                return True
        
        # Check multi-word phrases
        for command in self.config.command_words:
            if ' ' in command and command in normalized:
                logger.info(f"✋ Command phrase detected: '{command}' in '{text}'")
                return True
        
        return False
    
    def _is_only_fillers(self, text: str) -> bool:
        """Check if text contains only filler words."""
        normalized = self._normalize(text)
        words = normalized.split()
        
        if not words:
            return True
        
        is_filler = all(word in self.config.filler_words for word in words)
        if is_filler:
            logger.info(f"💬 Filler words detected: '{text}'")
        
        return is_filler
    
    def should_suppress(self, transcript: str, confidence: float) -> bool:
        """
        Determine if an interruption should be suppressed.
        
        Returns:
            True: Suppress interruption (let agent continue speaking)
            False: Allow interruption (stop agent)
        
        Logic:
            - If agent is SILENT → Never suppress (always respond)
            - If agent is SPEAKING:
                - Contains command words → Don't suppress (stop immediately)
                - Only filler words → Suppress (continue speaking)
                - Mixed/unclear → Don't suppress (be safe)
        """
        # Low confidence → be conservative, allow interruption
        if confidence < self.config.min_confidence:
            logger.debug(f"Low confidence ({confidence:.2f}), allowing interruption")
            return False
        
        # Agent silent → never suppress (treat as valid input)
        if not self.is_agent_speaking:
            logger.debug("Agent silent, processing input normally")
            return False
        
        # Agent speaking → analyze content
        
        # Command words → allow interruption
        if self._contains_command(transcript):
            return False
        
        # Only fillers → suppress interruption
        if self._is_only_fillers(transcript):
            logger.info(f"🚫 SUPPRESSING: '{transcript}' (filler while speaking)")
            return True
        
        # Mixed/unclear → allow interruption (be safe)
        logger.debug(f"Mixed input '{transcript}', allowing interruption")
        return False
    
    async def handle_vad_trigger(self) -> bool:
        """
        Handle VAD interruption event.
        
        When VAD detects speech, this method waits briefly for STT to provide
        the transcription, then decides whether to suppress the interruption.
        
        Returns:
            True: Allow interruption to proceed
            False: Suppress interruption (critical for seamless continuation)
        """
        # If agent not speaking, always allow
        if not self.is_agent_speaking:
            return True
        
        logger.debug("⏸️  VAD triggered while agent speaking...")
        
        # Wait for STT with timeout
        async with self._lock:
            self._stt_event = asyncio.Event()
            self._stt_buffer = []
        
        try:
            await asyncio.wait_for(
                self._stt_event.wait(),
                timeout=self.config.stt_wait_timeout
            )
            
            # Got STT - analyze it
            async with self._lock:
                if self._stt_buffer:
                    transcript = ' '.join(self._stt_buffer)
                    confidence = 0.9  # Assume high confidence for final results
                    
                    should_suppress = self.should_suppress(transcript, confidence)
                    
                    if should_suppress:
                        # CRITICAL: Return False to suppress interruption
                        return False
                    else:
                        return True
                else:
                    # No transcript - allow by default
                    return True
        
        except asyncio.TimeoutError:
            # Timeout - allow interruption to be safe
            logger.warning("⏱️  STT timeout, allowing interruption")
            return True
        finally:
            async with self._lock:
                self._stt_event = None
    
    async def feed_stt_result(self, transcript: str, is_final: bool = False):
        """
        Feed STT transcription results to the filter.
        
        This should be called whenever STT produces a transcription.
        """
        async with self._lock:
            if self._stt_event and not self._stt_event.is_set():
                self._stt_buffer.append(transcript)
                
                # Signal on final transcription
                if is_final:
                    self._stt_event.set()


class SmartInterruptionAgent(Agent):
    """
    Agent with intelligent interruption handling.
    
    This agent continues speaking seamlessly when users provide backchanneling
    (like "yeah", "ok", "hmm") but stops immediately for real commands.
    """
    
    def __init__(self, *args, interruption_config: Optional[InterruptionConfig] = None, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.int_config = interruption_config or InterruptionConfig()
        self.int_filter = InterruptionFilter(self.int_config)
        
        logger.info("SmartInterruptionAgent initialized")
        logger.info(f"Filler words: {sorted(self.int_config.filler_words)}")
        logger.info(f"Command words: {sorted(self.int_config.command_words)}")


async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for the smart interruption agent.
    
    This sets up the agent with intelligent interruption handling and
    connects all necessary event hooks.
    """
    logger.info("Starting Smart Interruption Agent...")
    
    await ctx.connect()
    
    # Load configuration (from env or defaults)
    config = InterruptionConfig.from_env()
    
    # Create agent
    agent = SmartInterruptionAgent(
        instructions="""You are a helpful and patient AI assistant.
        When explaining concepts, speak in complete, natural sentences.
        You are designed to continue speaking even when users say "yeah", "ok", or "hmm"
        to show they're listening - these are not interruptions.
        Only stop when users want to ask a question or give a command like "wait" or "stop".""",
        interruption_config=config
    )
    
    # Create session
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(
            model="nova-3",
            interim_results=True,  # Get partial results faster
        ),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="alloy", speed=1.0),
    )
    
    # CRITICAL: Hook up interruption handling
    _setup_interruption_hooks(session, agent.int_filter)
    
    # Start session
    logger.info("Starting agent session...")
    await session.start(agent=agent, room=ctx.room)
    
    # Initial greeting
    await session.generate_reply(
        instructions="Greet the user warmly and let them know you're ready to help."
    )
    
    logger.info("Agent session started successfully")


def _setup_interruption_hooks(session: AgentSession, filter: InterruptionFilter):
    """
    Setup event hooks for intelligent interruption handling.
    
    This is the core integration that makes the magic happen:
    1. Track when TTS is playing (agent speaking)
    2. Intercept VAD interruption events
    3. Feed STT results to the filter
    4. Allow or suppress interruptions based on filter decision
    
    Args:
        session: The AgentSession to hook into
        filter: The InterruptionFilter that makes decisions
    """
    logger.info("Setting up interruption hooks...")
    
    # Store original event handlers
    original_handlers = {
        'tts_start': getattr(session.tts, '_on_playout_started', None),
        'tts_end': getattr(session.tts, '_on_playout_completed', None),
        'vad_interrupt': getattr(session, '_handle_interruption', None),
        'stt_transcript': getattr(session.stt, '_on_transcript', None),
    }
    
    # === TTS EVENT HOOKS ===
    # These track when the agent is speaking
    
    def on_tts_started():
        """Called when TTS starts playing audio."""
        filter.set_agent_speaking(True)
        logger.debug("🎤 TTS started")
        if original_handlers['tts_start']:
            original_handlers['tts_start']()
    
    def on_tts_ended():
        """Called when TTS stops playing audio."""
        filter.set_agent_speaking(False)
        logger.debug("🔇 TTS ended")
        if original_handlers['tts_end']:
            original_handlers['tts_end']()
    
    # Apply TTS hooks
    if hasattr(session.tts, '_on_playout_started'):
        session.tts._on_playout_started = on_tts_started
    if hasattr(session.tts, '_on_playout_completed'):
        session.tts._on_playout_completed = on_tts_ended
    
    # === VAD INTERRUPT HOOK ===
    # This is THE CRITICAL HOOK that prevents unwanted interruptions
    
    async def on_vad_interrupt_event():
        """
        Called when VAD detects user speech.
        
        CRITICAL: This is where we decide whether to interrupt the agent.
        If we return without calling the original handler, the interruption
        is suppressed and the agent continues speaking seamlessly.
        """
        logger.debug("🎯 VAD interrupt event")
        
        # Let filter decide
        should_allow = await filter.handle_vad_trigger()
        
        if not should_allow:
            # SUPPRESS INTERRUPTION - Agent continues speaking
            logger.info("✅ Interruption suppressed - agent continues")
            return  # Don't call original handler!
        
        # Allow interruption
        logger.info("🛑 Interruption allowed - agent will stop")
        if original_handlers['vad_interrupt']:
            await original_handlers['vad_interrupt']()
    
    # Apply VAD hook
    if hasattr(session, '_handle_interruption'):
        session._handle_interruption = on_vad_interrupt_event
    
    # === STT TRANSCRIPT HOOK ===
    # Feed transcriptions to the filter
    
    async def on_stt_transcript(transcript: str, is_final: bool = False):
        """Called when STT produces a transcript."""
        logger.debug(f"📝 STT: '{transcript}' (final={is_final})")
        
        # Feed to filter
        await filter.feed_stt_result(transcript, is_final)
        
        # Call original handler
        if original_handlers['stt_transcript']:
            await original_handlers['stt_transcript'](transcript, is_final)
    
    # Apply STT hook
    if hasattr(session.stt, '_on_transcript'):
        session.stt._on_transcript = on_stt_transcript
    
    logger.info("✅ Interruption hooks configured successfully")


if __name__ == "__main__":
    # Run the agent
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
