import logging
import string

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
from livekit.agents.voice.events import UserInputTranscribedEvent
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
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        Ensure the user's location (city or region) is provided.
        When given a location, please estimate the latitude and longitude of the location and
        do not ask the user for them.

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
        preemptive_generation=True,
        resume_false_interruption=True,
        min_interruption_duration=1.0,
        false_interruption_timeout=1.0,
        discard_audio_if_uninterruptible=False,  # keep audio even if uninterruptible
        allow_interruptions=False,  # start with interruptions disabled
    )

    @session.on("user_input_transcribed")
    def on_transcription(ev: UserInputTranscribedEvent):
        BACKCHANNEL_WORDS = {"yeah", "ok", "okay", "hmm", "mhm", "sure", "right", "uh-huh"}
        # If the agent isn't speaking, we don't need to do anything
        if session.agent_state != "speaking":
            return

        # Clean up the text (remove punctuation, lower case)
        clean_text = (
            ev.transcript.translate(str.maketrans("", "", string.punctuation)).lower().strip()
        )
        words = clean_text.split()
        if not words:
            return
        is_only_backchannel = all(word in BACKCHANNEL_WORDS for word in words)

        if is_only_backchannel:
            print(f"Ignoring backchannel: '{clean_text}' - Agent continues speaking")
        else:
            print(f"Real interruption detected: '{clean_text}' - STOPPING AGENT")
            if session.current_speech:
                session.current_speech.allow_interruptions = True
                session.current_speech.interrupt()

    # log metrics as they are emitted, and total usage after session is over
    # usage_collector = metrics.UsageCollector()

    # @session.on("metrics_collected")
    # def _on_metrics_collected(ev: MetricsCollectedEvent):
    #     metrics.log_metrics(ev.metrics)
    #     usage_collector.collect(ev.metrics)

    # async def log_usage():
    #     summary = usage_collector.get_summary()
    #     logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    # ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # uncomment to enable the Krisp BVC noise cancellation
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
