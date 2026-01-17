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

# --- CONFIGURATION ---
# Configurable Ignore List
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
    Logic layer for Semantic Interruption.
    Determines if a partial transcript warrants stopping the agent.
    """
    def __init__(self, ignore_words: list = None, interrupt_words: list = None):
        self.ignore_words: Set[str] = set(w.lower() for w in (ignore_words or IGNORE_WORDS))
        self.interrupt_words: Set[str] = set(w.lower() for w in (interrupt_words or INTERRUPT_WORDS))
        self.agent_state = AgentState.IDLE
        
        self.stats = {
            'ignored_backchannel': 0,
            'allowed_interrupts': 0,
        }
    
    def set_state(self, state: AgentState):
        self.agent_state = state
    
    def _normalize(self, text: str) -> str:
        import re
        return re.sub(r'[^\w\s]', '', text.lower().strip())

    def should_interrupt(self, text: str) -> bool:
        """
        Decides if we should FORCE an interruption based on partial text.
        
        Returns:
            True: VALID interruption (User said "Stop", "Wait", or a full sentence).
            False: IGNORE (User said "Yeah", "Ok").
        """
        if not text or not text.strip():
            return False
            
        norm_text = self._normalize(text)
        words = norm_text.split()
        
        # 1. Check for explicit interrupt commands
        # (e.g. "Stop", "Wait")
        if any(w in norm_text for w in self.interrupt_words):
            self.stats['allowed_interrupts'] += 1
            return True
            
        # 2. Check for Ignore Words (Backchanneling)
        # If the input contains ONLY ignore words, we return False (Do not interrupt).
        if all(w in self.ignore_words for w in words if w):
            self.stats['ignored_backchannel'] += 1
            logger.info(f"🙈 DETECTED BACKCHANNEL: '{text}' -> Ignoring")
            return False
            
        # 3. Default: If it's not a backchannel and not a stop word, 
        # it's likely a valid question or sentence. Interrupt.
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
        # When idle, we always listen
        self.allow_interruptions = True
        await self.session.generate_reply()
    
    # --- RETAINED YOUR WEATHER TOOL ---
    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information."""
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    
    # Initialize Guard
    guard = InterruptionGuard(
        ignore_words=IGNORE_WORDS,
        interrupt_words=INTERRUPT_WORDS
    )
    
    session = AgentSession(
        stt="deepgram/nova-3", # Ensure fast STT model
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )
    
    # --- RETAINED YOUR METRICS LOGIC ---
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
        logger.info(f"Interruption Logic Stats: {guard.stats}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Create agent
    agent = MyAgent(guard)
    
    # ---------------------------------------------------------
    #  CORE ASSIGNMENT LOGIC (Active Ignore Strategy)
    # ---------------------------------------------------------

    @session.on("agent_started_speaking")
    def _on_agent_started_speaking():
        guard.set_state(AgentState.SPEAKING)
        # STRATEGY CHANGE: Default to Deny. 
        # We explicitly DISABLE interruptions so VAD doesn't trigger pauses on "yeah".
        agent.allow_interruptions = False
        logger.info("🗣️  AGENT SPEAKING -> Interruptions DISABLED (Monitoring STT)")
    
    @session.on("agent_stopped_speaking")
    def _on_agent_stopped_speaking():
        guard.set_state(AgentState.IDLE)
        # When silent, we must respond to "Yeah" (Passive Affirmation Scenario)
        agent.allow_interruptions = True
        logger.info("🤐 AGENT STOPPED -> Interruptions ENABLED")
    
    @session.on("user_started_speaking")
    def _on_user_started_speaking():
        # Just logging - the actual logic is in transcript_updated
        if guard.agent_state == AgentState.SPEAKING:
            logger.debug("🎤 User speaking over agent... checking validity...")
    
    @session.on("user_transcript_updated")
    def _on_user_transcript_updated(transcript):
        """
        Handles the "False Start" interruption.
        This runs on PARTIAL transcripts (very fast).
        """
        # If we are already allowing interruptions (IDLE), do nothing.
        if agent.allow_interruptions:
            return

        if not hasattr(transcript, 'text') or not transcript.text:
            return
            
        partial_text = transcript.text
        
        # Check if we should force an interrupt
        if guard.should_interrupt(partial_text):
            logger.info(f"🛑 VALID INTERRUPTION: '{partial_text}' -> Stopping Agent")
            
            # 1. Enable interruptions immediately so the system takes over
            agent.allow_interruptions = True
            
            # 2. Trigger the interrupt
            if hasattr(agent, 'interrupt'):
                asyncio.create_task(agent.interrupt())
        else:
            # If should_interrupt returns False, we do NOTHING.
            # allow_interruptions remains False.
            # The agent continues speaking over the "yeah" without pausing.
            pass

    @session.on("user_speech_committed")
    def _on_user_speech_committed(message):
        """
        Final transcription. Ensure we reset state if needed.
        """
        # Always re-enable interruptions after a full turn is processed
        # to ensure we don't get stuck in a "deaf" state.
        if guard.agent_state == AgentState.IDLE:
             agent.allow_interruptions = True
        
        text = message.text if hasattr(message, 'text') else str(message)
        logger.info(f"📋 FINAL TRANSCRIPT: '{text}'")

    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)