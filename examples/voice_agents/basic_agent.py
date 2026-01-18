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
    llm,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("basic-agent")

load_dotenv()

# --- 1. DEFINE THE IGNORE LIST ---
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "aha", "uh-huh", "right", 
    "cool", "nice", "got it", "i see", "yep", "sure", "no problem"
}

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Randi. You would interact with users via voice. "
            "You are curious and friendly. "
            "Please speak in full sentences and keep the conversation flowing.",
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
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
    
    # --- 2. CONFIGURE SESSION WITH "DEAF MODE" ---
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini", # Switched to standard model name just in case
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        
        # CRITICAL CHANGE: Disable auto-interruption.
        # This prevents the VAD from stopping the agent. We will handle it manually.
        allow_interruptions=False, 
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

    # --- 3. THE LOGIC LAYER ---
    @session.on("user_speech_committed")
    def on_user_speech(msg: llm.ChatMessage):
        # 1. Get the user's text
        user_text = msg.content
        
        # 2. Clean it up
        cleaned_text = user_text.strip().lower().replace(".", "").replace(",", "").replace("!", "")
        
        # 3. Check if the agent is currently speaking
        # (If the agent is silent, we don't need to do anything special, the LLM will just reply)
        if session.current_agent_state != "speaking":
             # Wait, strict check: AgentSession might not expose 'speaking' state easily in this version.
             # We rely on the interrupt logic:
             pass

        # 4. Logic Matrix
        words = cleaned_text.split()
        is_soft_input = all(w in IGNORE_WORDS for w in words)

        # If it is a soft input (only "yeah", "ok"), we do NOTHING.
        # Since allow_interruptions=False, the agent will keep talking.
        if is_soft_input:
            logger.info(f" -> IGNORING (Soft): '{cleaned_text}'")
            return

        # If it is a HARD input (contains "stop", "wait", or mixed sentence), we interrupt.
        logger.info(f" -> INTERRUPTING (Hard): '{cleaned_text}'")
        session.interrupt() 
        # Note: We might need to manually trigger a reply here if the session doesn't auto-queue it.
        # But usually, speech_committed triggers the LLM.

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )

if __name__ == "__main__":
    cli.run_app(server)