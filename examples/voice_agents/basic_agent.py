import logging
import os
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
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero, deepgram, google

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("basic-agent")

load_dotenv()

# --- STOP COMMAND PHRASES (positive) ---
STOP_PHRASES = [
    "stop",
    "please stop",
    "stop talking",
    "wait",
    "hold on",
    "pause",
    "cancel",
    "listen",
    "shut up",
    "hey kelly",
    "kelly stop",
]

# --- NEGATED PHRASES THAT SHOULD *NOT* STOP ---
NEGATED_STOP_PHRASES = [
    "don't stop",
    "do not stop",
    "not stop",
    "not stopping",
    "never stop",
]


def is_stop_command(text: str) -> bool:
    """Return True only if text should be treated as a real STOP command."""
    t = text.lower()

    # 1) If any explicit negation is present, do NOT treat as stop
    if any(neg in t for neg in NEGATED_STOP_PHRASES):
        return False

    # 2) Otherwise, look for any positive stop phrase
    return any(phrase in t for phrase in STOP_PHRASES)


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Keep your responses concise but helpful. "
                "You are curious and friendly. "
                "Speak English."
            ),
        )

    async def on_enter(self):
        # First greeting – seed the LLM with a clear instruction
        await self.session.generate_reply(
            user_input="Greet the user warmly and introduce yourself as Kelly."
        )

    @function_tool
    async def lookup_weather(
        self,
        context: RunContext,
        location: str,
        latitude: str,
        longitude: str,
    ):
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    # Load VAD to prevent startup errors, but we won't use it actively
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    await ctx.connect()
    ctx.log_context_fields = {"room": ctx.room.name}

    api_key = os.getenv("GOOGLE_API_KEY")

    my_agent = MyAgent()

    session = AgentSession(
        stt=deepgram.STT(
            model="nova-3",
            interim_results=True,
        ),
        llm=google.LLM(
            model="gemini-2.0-flash",
            api_key=api_key,
        ),
        tts=deepgram.TTS(),
        # --- DEAF AGENT: no automatic turn detection ---
        turn_detection=None,
        vad=None,
        preemptive_generation=False,   # we call generate_reply manually
        allow_interruptions=False,     # NO auto barge-in
        discard_audio_if_uninterruptible=False,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent):
        text = (ev.transcript or "").lower()
        is_final = ev.is_final

        print(f"👂 Heard: '{text}' (Final: {is_final})")

        if not text.strip():
            return  # ignore empty/noise

        # --- 1. STOP COMMAND HANDLING ---
        if is_stop_command(text):
            print(f" STOP COMMAND DETECTED: '{text}'")
            # Force interruption even though allow_interruptions=False
            try:
                session.interrupt(force=True)
            except Exception as e:
                print(f" Error interrupting: {e}")
            return

        # --- 2. IGNORE FILLERS WHILE KELLY IS SPEAKING ---
        if session.current_speech is not None:
            print(" Agent is speaking – ignoring user speech (no stop command).")
            return

        # --- 3. NORMAL REPLY ON FINAL SENTENCE ---
        if is_final:
            print("End of sentence detected. Replying with full text...")
            # Pass what the user actually said to the LLM
            session.generate_reply(user_input=text)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=my_agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
