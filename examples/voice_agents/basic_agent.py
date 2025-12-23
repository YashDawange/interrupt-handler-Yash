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

# ========== ADD THIS IMPORT ==========
from interrupt_controller import InterruptController
# =====================================

logger = logging.getLogger("basic-agent")
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
        # ========== ADD THIS ==========
        self.interrupt_ctrl = InterruptController()
        # ==============================

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
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # ========== ADD THESE EVENT HANDLERS ==========
    agent_instance = MyAgent()
    
    @session.on("user_speech_committed")
    def on_user_speech(text: str):
        """Intercept user speech before LLM"""
        should_interrupt, override_response = agent_instance.interrupt_ctrl.should_interrupt(text)
        
        if not should_interrupt:
            if override_response:
                # Agent responds directly (for "yeah" when waiting)
                session.say(override_response, allow_interruptions=False)
            else:
                # Completely ignore (backchannel while speaking)
                logger.info(f"[BACKCHANNEL IGNORED] {text}")
            # Stop processing - don't send to LLM
            return False
        # Continue normal processing
        return True
    
    @session.on("agent_started_speaking")
    def on_agent_start_speak():
        agent_instance.interrupt_ctrl.on_agent_started_speaking()
    
    @session.on("agent_stopped_speaking")
    def on_agent_stop_speak():
        agent_instance.interrupt_ctrl.on_agent_stopped_speaking()
    
    # ===============================================

    await session.start(
        agent=agent_instance,  # Use the instance we created
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
