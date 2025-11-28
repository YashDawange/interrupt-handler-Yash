import logging
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hybrid-agent")

load_dotenv()

# Words that FORCE interruption
INTERRUPT_KEYWORDS = {"stop", "wait", "pause", "hold on", "no", "cancel"}

class HybridAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are Kelly. Speak naturally and do NOT pause waiting for the user."
        )

    async def on_enter(self):
        self.session.generate_reply()

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        allow_interruptions=False  # <-- KEY PART
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _metrics(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    @session.on("transcription")
    async def on_transcription(text: str, lang: str):
        cleaned = text.lower().strip()

        # If agent is speaking and user says interrupt command → force stop
        if any(word in cleaned for word in INTERRUPT_KEYWORDS):
            print(f"[ INTERRUPTION DETECTED: {cleaned} ]")
            session.stop_speaking()
            await session.generate_response("Okay, stopping. What would you like instead?")
            return

        print(f"[ USER SAID: {cleaned} ]")

    await session.start(
        agent=HybridAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions()
    )


if __name__ == "__main__":
    cli.run_app(server)
