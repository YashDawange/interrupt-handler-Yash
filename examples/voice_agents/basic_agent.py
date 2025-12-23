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
    UserInputTranscribedEvent,
    AgentStateChangedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from backchannel_handler import SmartInterruptionHandler

# Initialize logging subsystem
logger = logging.getLogger("voice-assistant")
load_dotenv()


class ConversationalAssistant(Agent):
    """
    Full-featured conversational AI agent with natural interaction capabilities.
    Designed to handle broad topic discussions while maintaining conversational flow.
    """
    
    def __init__(self) -> None:
        """Configure agent personality and behavioral guidelines."""
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
        """
        Lifecycle hook: executed when agent joins the session.
        Triggers initial greeting generation based on instructions.
        """
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self,
        context: RunContext,
        location: str,
        latitude: str,
        longitude: str,
    ):
        """
        Weather information retrieval tool.
        
        Usage Policy:
        - Only invoke when user explicitly requests weather data
        - Do not use for general conversation or explanations
        - Suitable for queries about: temperature, forecast, precipitation, humidity
        
        Args:
            location: Human-readable location name
            latitude: Geographic latitude coordinate
            longitude: Geographic longitude coordinate
        
        Returns:
            Weather information string
        """
        logger.info(f"Weather query for location: {location}")
        return "It is currently sunny with a temperature of 70 degrees."


# Initialize agent server instance
server = AgentServer()


def prewarm(proc: JobProcess):
    """
    Worker process initialization hook.
    Pre-loads heavy resources (like VAD model) once per process
    to avoid repeated loading overhead during conversations.
    """
    logger.info("Pre-warming worker process with VAD model")
    proc.userdata["vad"] = silero.VAD.load()


# Register prewarm function
server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """
    Session entry point: orchestrates the entire conversation lifecycle.
    Sets up all components, event handlers, and starts the agent session.
    """
    
    # Configure structured logging with room context
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info(f"Starting new session in room: {ctx.room.name}")

    # ==========================================
    # SESSION CONFIGURATION
    # ==========================================
    session = AgentSession(
        # Speech-to-Text provider and model
        stt="deepgram/nova-3",
        
        # Language model for conversation
        llm="google/gemini-2.5-flash",
        
        # Text-to-Speech provider and voice
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        
        # Turn detection for natural conversation flow
        turn_detection=MultilingualModel(),
        
        # Voice Activity Detection (pre-loaded)
        vad=ctx.proc.userdata["vad"],
        
        # Enable proactive response generation
        preemptive_generation=True,
        
        # Interruption behavior (framework-level)
        allow_interruptions=True,
        discard_audio_if_uninterruptible=True,
        
        # Fine-tuning interruption sensitivity
        min_interruption_duration=0.6,   # seconds of speech required
        min_interruption_words=2,         # minimum word count for interruption
    )

    # ==========================================
    # SMART INTERRUPTION SYSTEM INITIALIZATION
    # ==========================================
    interruption_handler = SmartInterruptionHandler()
    logger.info("Smart interruption system activated")

    # ==========================================
    # TELEMETRY AND METRICS COLLECTION
    # ==========================================
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def handle_metrics_collection(event: MetricsCollectedEvent):
        """
        Process and log collected metrics from the session.
        Tracks usage for monitoring and optimization.
        """
        metrics.log_metrics(event.metrics)
        usage_collector.collect(event.metrics)

    async def log_session_summary():
        """
        Shutdown callback: logs final usage summary.
        Called automatically when session ends.
        """
        summary = usage_collector.get_summary()
        logger.info(f"Session completed. Usage summary: {summary}")

    ctx.add_shutdown_callback(log_session_summary)

    # ==========================================
    # EVENT HANDLERS FOR INTERRUPTION LOGIC
    # ==========================================

    @session.on("agent_state_changed")
    def handle_agent_state_transition(event: AgentStateChangedEvent):
        """
        Monitor agent state transitions to track when agent is speaking.
        
        States: initializing → listening → thinking → speaking
        The 'speaking' state is crucial for interruption decisions.
        """
        currently_speaking = (event.new_state == "speaking")
        interruption_handler.update_agent_speaking_state(currently_speaking)
        
        logger.debug(
            f"Agent transitioned: {event.old_state} → {event.new_state}"
        )

    @session.on("user_input_transcribed")
    def handle_user_speech(event: UserInputTranscribedEvent):
        """
        Process incoming user speech transcripts with intelligent interruption logic.
        
        Strategy:
        - Allow normal flow when agent is silent (user can respond freely)
        - Filter out acknowledgments when agent is speaking (maintain flow)
        - Interrupt immediately on explicit commands or substantive input
        
        This creates a natural conversation where users can acknowledge
        without disrupting the agent, but can also interrupt when needed.
        """
        transcript = (event.transcript or "").strip()
        
        # Analyze transcript and get interruption decision
        should_interrupt, reason = interruption_handler.should_interrupt(
            transcript, 
            event.is_final
        )
        
        # Execute appropriate action based on decision
        if reason == "soft_backchannel":
            # Acknowledgment detected: clear from history to prevent echo
            logger.debug(f"Filtered acknowledgment: '{transcript}'")
            session.clear_user_turn()
            return
        
        if should_interrupt:
            # Real interruption: stop agent and process user input
            logger.info(f"User interrupted agent: '{transcript}' (reason: {reason})")
            session.interrupt(force=True)
            return
        
        # Normal processing: let framework handle it naturally
        # (This covers cases where agent isn't speaking)

    # ==========================================
    # SESSION STARTUP
    # ==========================================
    logger.info("Launching agent session")
    await session.start(
        agent=ConversationalAssistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # Optional: noise cancellation can be enabled here
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)