import logging
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

# Import your handler
from interrupt_handler import IntelligentInterruptionHandler

logger = logging.getLogger("basic-agent")
logger.setLevel(logging.INFO)
load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice."
            "with that in mind keep your responses concise and to the point."
            "do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "you will speak english to the user",
        )
        # Initialize the interruption handler
        self.interrupt_handler = IntelligentInterruptionHandler()
        self._is_speaking = False

    async def on_enter(self):
        self.session.generate_reply()

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
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    agent = MyAgent()
    
    # Create session with optimized settings for interruption handling
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),  # Don't pass custom params here
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        # KEY SETTINGS for interruption handling:
        resume_false_interruption=True,  # Resume if it was a false interruption
        false_interruption_timeout=2.5,  # Increased from 1.0 to 2.5 seconds
        min_interruption_words=2,  # Require at least 2 words to interrupt (ignores single "yeah")
        allow_interruptions=True,
    )
    
    # Track agent speaking state with events
    @session.on("agent_started_speaking")
    def on_agent_started_speaking(event):
        agent._is_speaking = True
        agent.interrupt_handler.set_agent_speaking_state(True)
        logger.info("🗣️  [AGENT] Started speaking")
    
    @session.on("agent_stopped_speaking")
    def on_agent_stopped_speaking(event):
        agent._is_speaking = False
        agent.interrupt_handler.set_agent_speaking_state(False)
        logger.info("🤐 [AGENT] Stopped speaking")
    
    # Monitor user speech
    @session.on("user_started_speaking")
    def on_user_started_speaking(event):
        logger.info(f"👤 [USER] Started speaking (Agent is {'SPEAKING' if agent._is_speaking else 'SILENT'})")
    
    @session.on("user_stopped_speaking")
    def on_user_stopped_speaking(event):
        logger.info(f"👤 [USER] Stopped speaking")
    
    # Process transcriptions with intelligent filtering
    @session.on("user_speech_committed")
    def on_user_speech_committed(event):
        # Get transcription
        transcription = event.alternatives[0].text if event.alternatives else ""
        
        logger.info(f"")
        logger.info(f"{'='*70}")
        logger.info(f"📝 [TRANSCRIPTION] User said: '{transcription}'")
        logger.info(f"🤖 [STATE] Agent is currently: {'SPEAKING' if agent._is_speaking else 'SILENT'}")
        
        # Use our intelligent handler to decide
        should_interrupt = agent.interrupt_handler.process_transcription(
            transcription, 
            agent._is_speaking
        )
        
        if should_interrupt:
            logger.info(f"✅ [DECISION] ALLOWING interruption")
        else:
            logger.info(f"🚫 [DECISION] BLOCKING interruption (backchannel detected)")
        
        logger.info(f"{'='*70}")
        logger.info(f"")
    
    # Metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
