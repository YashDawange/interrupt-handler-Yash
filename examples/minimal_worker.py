import logging

from dotenv import load_dotenv
from interrupt_filter import InterruptFilter
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

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

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

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        Ensure the user's location (city or region) is provided.
        When given a location, please estimate the latitude and longitude of the location and
        do not ask the user for them.
        """

        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=False,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    # ---------------- INTERRUPTION HANDLING STATE ----------------
    interrupt_filter = InterruptFilter()
    agent_speaking = False
    # ------------------------------------------------------------

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # ---------------- AGENT SPEAKING STATE ----------------
    @session.on("agent_started_speaking")
    def _on_agent_started(_):
        nonlocal agent_speaking
        agent_speaking = True

    @session.on("agent_stopped_speaking")
    def _on_agent_stopped(_):
        nonlocal agent_speaking
        agent_speaking = False
    # ------------------------------------------------------

    # ---------------- CORE INTERRUPTION LOGIC ----------------
    @session.on("transcription")
    def _on_transcription(ev):
        if ev.type != "user":
            return

        if not ev.segment or not ev.segment.text:
            return

        text = ev.segment.text.lower()
        is_final = ev.segment.final

        # 🔴 AGENT IS SPEAKING
        if agent_speaking:
            # We do NOTHING until STT confirms intent
            if is_final and interrupt_filter.is_hard_interrupt(text):
                logger.info(f"HARD INTERRUPT CONFIRMED: {text}")
                session.interrupt()
            else:
                logger.info(f"IGNORED WHILE SPEAKING: {text}")
            return

        # 🟢 AGENT IS SILENT
        if is_final:
            logger.info(f"USER INPUT (SILENT): {text}")
            session.generate_reply()
        
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
