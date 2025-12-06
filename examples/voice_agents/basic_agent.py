import logging
import os
from dotenv import load_dotenv
import asyncio
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

# -----------------------
# CONFIG
# -----------------------
IGNORE_LIST = {'yeah', 'ok', 'hmm', 'right', 'uh-huh', 'okay', 'yep', 'aha', 'mhm', 'mm-hmm', 'uh', 'hm'}
INTERRUPT_KEYWORDS = {'wait', 'stop', 'no', 'cancel', 'hold', 'pause', 'but'}

logger = logging.getLogger("basic-agent")
logging.basicConfig(level=logging.INFO)

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)


# -----------------------
# SMART FILTER
# -----------------------
class SmartInterruptFilter:
    def __init__(self):
        self.agent_is_speaking = False
        self.should_block_next = False
        
    def set_speaking(self, is_speaking: bool):
        self.agent_is_speaking = is_speaking
        logger.info(f"{'🎙️ Agent STARTED' if is_speaking else '🔇 Agent STOPPED'} speaking")
    
    def check_if_should_block(self, text: str) -> bool:
        """Check if this text should be blocked from interrupting"""
        if not text or not text.strip():
            return False
            
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        # If agent NOT speaking, never block
        if not self.agent_is_speaking:
            logger.info(f"✅ Agent silent - allowing: '{text}'")
            return False
        
        # Check for interrupt keywords
        has_interrupt = any(kw in text_lower for kw in INTERRUPT_KEYWORDS)
        if has_interrupt:
            logger.info(f"🛑 INTERRUPT keyword: '{text}'")
            return False  # Don't block, allow interrupt
        
        # Check if ALL words are fillers
        non_filler = [w for w in words if w and w not in IGNORE_LIST]
        
        if len(non_filler) == 0:
            logger.info(f"🛡️ BLOCKING filler: '{text}'")
            return True  # Block this
        else:
            logger.info(f"🔄 Real content: '{text}'")
            return False  # Don't block


# -----------------------
# AGENT DEFINITION
# -----------------------
class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Keep your responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or other special characters. "
                "Be curious and friendly, with a sense of humor. "
                "Speak English."
            )
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."


# -----------------------
# AGENT SERVER
# -----------------------
server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm


# -----------------------
# ENTRYPOINT
# -----------------------
@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    
    interrupt_filter = SmartInterruptFilter()

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
        preemptive_generation=True,
        allow_interruptions=True,
        
        # CRITICAL: Require 2 words before interrupting
        # This naturally filters single-word fillers
        min_interruption_words=2,
        min_interruption_duration=0.6,
        
        # Use false interruption recovery
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
    )

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

    # ------------------------------
    # Track agent speaking
    # ------------------------------
    @session.on("agent_started_speaking")
    def on_agent_started_speaking(ev):
        interrupt_filter.set_speaking(True)

    @session.on("agent_stopped_speaking")
    def on_agent_stopped_speaking(ev):
        interrupt_filter.set_speaking(False)

    # ------------------------------
    # Monitor and log transcriptions
    # ------------------------------
    last_text = {"text": "", "timestamp": 0}
    
    @session.on("user_speech_committed")
    def on_user_speech_committed(ev):
        """Log user speech and check filter"""
        import time
        
        if not ev.alternatives or len(ev.alternatives) == 0:
            return
            
        user_text = ev.alternatives[0].text.strip()
        current_time = time.time()
        
        # Avoid duplicates
        if user_text == last_text["text"] and current_time - last_text["timestamp"] < 1.0:
            return
            
        last_text["text"] = user_text
        last_text["timestamp"] = current_time
        
        logger.info(f"💬 User: '{user_text}' (agent_speaking={interrupt_filter.agent_is_speaking})")
        
        # Check what we WOULD do with this
        should_block = interrupt_filter.check_if_should_block(user_text)
        
        if should_block:
            logger.info("🚫 This should have been blocked (but min_interruption_words=2 helps)")

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions()
        ),
    )


# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    cli.run_app(server)