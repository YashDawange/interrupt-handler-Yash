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

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

load_dotenv()

agent_is_speaking = False

IGNORE_WORDS = {"yeah", "ok", "hmm", "uh-huh"}
INTERRUPT_WORDS = {"stop", "wait", "no"}


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

    @session.on("user_transcript")
    async def _on_user_transcript(text: str):
     global agent_is_speaking
     text = text.lower().strip()

     # Case 1: Agent speaking + filler word → IGNORE
     if agent_is_speaking and text in IGNORE_WORDS:
        print("[IGNORED while speaking]:", text)
        return

    # Case 2: Agent speaking + interrupt command → STOP
     if agent_is_speaking and any(w in text for w in INTERRUPT_WORDS):
        print("[INTERRUPT]:", text)
        await session.stop_agent_speech()
        return

    # Case 3: Agent silent + filler → RESPOND
     if not agent_is_speaking and text in IGNORE_WORDS:
        print("[RESPOND while silent]:", text)


    @session.on("agent_speech_started")
    def _on_agent_speech_started():
     global agent_is_speaking
     agent_is_speaking = True
     print("[AGENT SPEAKING]")

    @session.on("agent_speech_finished")
    def _on_agent_speech_finished():
     global agent_is_speaking
     agent_is_speaking = False
     print("[AGENT SILENT]")



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
