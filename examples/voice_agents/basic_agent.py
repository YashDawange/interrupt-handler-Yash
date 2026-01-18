import logging

from dotenv import load_dotenv

from livekit.plugins import silero, openai, deepgram
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
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("basic-agent")

load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice. "
            "With that in mind keep your responses concise and to the point. "
            "Do not use emojis, asterisks, markdown, or other special characters in your responses. "
            "You are curious and friendly, and have a sense of humor. "
            "You will speak english to the user.",
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        
        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """
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
    
    # Create session with the interruption_speech_filter in options
    session = AgentSession(
        stt="deepgram/nova-3",
        llm=openai.LLM.with_azure(
            model="gpt-4o-mini",
            azure_deployment="gpt-4o-mini",
        ),
        tts=deepgram.TTS(),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )
    
    # Set the interruption_speech_filter in session options
    # This is the key - we need to set it on the session.options object
    session.options.interruption_speech_filter = {
        "yeah", "yes", "yep", "yup", "ya",
        "ok", "okay", "k",
        "hmm", "hmmm", "mhmm", "mm-hmm", "mmhmm",
        "uh-huh", "uh", "um", "uhm",
        "right", "sure", "aha", "ah", "oh",
    }
    
    # Important: Set resume_false_interruption to False to prevent pause/resume behavior
    session.options.resume_false_interruption = False
    
    # Optionally adjust the false interruption timeout
    session.options.false_interruption_timeout = 1.0

    # Log metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)