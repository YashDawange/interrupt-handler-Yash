import logging
import string  # [ADDED] Required for text cleaning

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
# [ADDED] Required to detect transcript events
from livekit.agents.stt import SpeechEventType 
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

load_dotenv()

# [ADDED] Step 1: Define words that should NOT trigger an interruption
IGNORE_WORDS = {
    "yeah", 
    "ok", 
    "hmm", 
    "uh-huh", 
    "right", 
    "aha", 
    "okay", 
    "sure",
    "i see",
    "go on"
}

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is jordy101. You would interact with users via voice."
            "with that in mind keep your responses concise and to the point."
            "do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "you will speak english to the user",
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

    # [ADDED] Step 3: The Logic Layer
    # This function intercepts the transcription stream to decide on interruptions

# [FINAL VERSION] Step 3 & 4: Logic Layer + Response Filter
    async def stt_node(self, audio_stream, model_settings):
        # We wrap the default STT logic
        async for event in super().default.stt_node(self, audio_stream, model_settings):
            # We only care about transcript events (Interim or Final)
            if event.type == SpeechEventType.FINAL_TRANSCRIPT or event.type == SpeechEventType.INTERIM_TRANSCRIPT:
                # 1. Get the text and clean it
                if event.alternatives and event.alternatives[0].text:
                    text = event.alternatives[0].text.strip().lower()
                    clean_text = text.translate(str.maketrans('', '', string.punctuation))

                    # 2. Check if the agent is currently speaking
                    is_speaking = False
                    if self.session.current_speech and not self.session.current_speech.done():
                         is_speaking = True

                    # 3. Decision Matrix
                    if is_speaking:
                        # Case A: Active Interruption (e.g., "Stop")
                        # Action: Interrupt immediately.
                        if clean_text not in IGNORE_WORDS and clean_text != "":
                            await self.session.current_speech.interrupt(force=True)
                        
                        # [ADDED] Step 4: Response Filter
                        # Case B: Passive Acknowledgement (e.g., "Yeah")
                        # Action: If it's a FINAL transcript, DROP IT so the LLM doesn't reply.
                        elif clean_text in IGNORE_WORDS and event.type == SpeechEventType.FINAL_TRANSCRIPT:
                            continue # Skip yielding this event -> System ignores it completely.

            # Always yield the event back (unless we hit Case B above)
            yield event

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

        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 120 degree celcius."


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
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt="deepgram/nova-3",
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm="openai/gpt-4.1-mini",
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
        # when it's detected, you may resume the agent's speech
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        # [ADDED] Step 2: Disable default VAD interruption
        allow_interruptions=False
    )

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

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