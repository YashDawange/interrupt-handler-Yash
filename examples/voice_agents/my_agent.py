import logging
from dotenv import load_dotenv

from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from intelligent_agent_comp import IntelligentInterruptionAgent 

logger = logging.getLogger("basic-agent")

load_dotenv()

server = AgentServer()

# --- PREWARM DISABLED TO PREVENT 429 ERRORS ---
# def prewarm(proc: JobProcess):
#     proc.userdata["vad"] = silero.VAD.load()
# server.setup_fnc = prewarm
# ----------------------------------------------

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # Log room context
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # FIX: Load VAD directly here since prewarm is disabled
    # This prevents the KeyError: 'vad'
    vad_model = silero.VAD.load()


    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=vad_model,                 # <--- Use the locally loaded model
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

    agent_instructions = (
        "Your name is Kelly. You would interact with users via voice."
        "with that in mind keep your responses concise and to the point."
        "do not use emojis, asterisks, markdown, or other special characters in your responses."
        "You are curious and friendly, and have a sense of humor."
        "you will speak english to the user"
    )

    await session.start(
        agent=IntelligentInterruptionAgent(
             instructions=agent_instructions, 
        ),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )

if __name__ == "__main__":
    cli.run_app(server)
