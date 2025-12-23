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

# Import our custom backchannel handler
from backchannel_handler import BackchannelInterruptHandler

logger = logging.getLogger("basic-agent")
load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
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
        """When the agent is added to the session, generate initial reply."""
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
        OPTIONAL helper tool.
        Use this tool ONLY when the user explicitly asks for weather information
        (e.g., temperature, forecast, rain, humidity).
        Do NOT use this tool for general conversation or explanations.
        """
        logger.info(f"Weather tool invoked for location: {location}")
        return "It is currently sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    """Load VAD once per worker process."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entry point for the agent session."""
    
    # Set up logging context
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # ===========
    # AGENT SESSION SETUP
    # ===========
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="google/gemini-2.5-flash",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        allow_interruptions=True,
        discard_audio_if_uninterruptible=True,
        min_interruption_duration=0.6,
        min_interruption_words=2,
    )

    # ===========
    # INITIALIZE BACKCHANNEL HANDLER
    # ===========
    interrupt_handler = BackchannelInterruptHandler()

    # ===========
    # METRICS LOGGING
    # ===========
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # ===========
    # INTELLIGENT INTERRUPTION LAYER
    # ===========

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        """Track agent speaking state for interruption logic."""
        is_speaking = ev.new_state == "speaking"
        interrupt_handler.update_agent_speaking_state(is_speaking)
        logger.debug("Agent state changed: %s -> %s", ev.old_state, ev.new_state)

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        """
        Handle user input with intelligent interruption logic.
        
        Core logic:
        - If the agent is NOT speaking → do nothing, let normal behavior happen.
        - If the agent IS speaking:
            * If final transcript is only backchannel words → ignore.
            * If final transcript contains interrupt words or non-backchannel → interrupt.
        """
        text = (ev.transcript or "").strip()
        
        # Use the handler to determine if we should interrupt
        should_interrupt, reason = interrupt_handler.should_interrupt(text, ev.is_final)
        
        if reason == "soft_backchannel":
            # Clear the current user turn so these words are not committed
            session.clear_user_turn()
            return
        
        if should_interrupt:
            # Force interruption for strong interrupts or mixed input
            session.interrupt(force=True)
            return
        
        # Otherwise, let normal session behavior handle it

    # ===========
    # START SESSION
    # ===========
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # noise_cancellation=noise_cancellation.BVC(),  # optional
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)