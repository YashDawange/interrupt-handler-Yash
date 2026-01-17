import logging

import re
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
from livekit.agents import UserStateChangedEvent, AgentStateChangedEvent
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import UserInputTranscribedEvent
# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation
from livekit import rtc
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


def should_interrupt(text: str) -> bool:
    """
    Return True if this transcription should interrupt the agent.
    """

    # If agent is not speaking, ANY speech is considered valid.


    ignored_fillers="uh,umm,hmm,haan,um,ah,er,like,yeah,mhm,mm,mhmm,uh-huh"
    stop_words="stop,wait,holdon"
    ignored_fillers = [w.strip() for w in ignored_fillers.split(",") if w.strip()]
    stop_words = [w.strip() for w in stop_words.split(",") if w.strip()]
    # Basic "low-confidence" / noise heuristic when confidence is not available:
    # treat extremely short transcripts as background murmur.
    normalized = text.strip()
    if len(normalized) < 2:
        return False

    # Tokenize into alphabetic words
    words = re.findall(r"[a-zA-Z]+", normalized.lower())

    if not words:
        # No recognizable words -> treat as noise
        return False

    # If there is at least one non-filler word, treat this as a real interruption.
    for w in words:
        if w in stop_words:
            return True
        if w not in ignored_fillers:
            return True

    # All words are fillers from the ignored list -> ignore.
    return False


    

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    agent_flag=False
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
        turn_detection=None,
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        allow_interruptions=True,
        # Significantly increase the required speech duration to effectively disable VAD auto-interrupt
        # We'll manually control interruptions based on transcript content
        min_interruption_duration=5.0,  # Very high - VAD won't auto-interrupt for normal speech
        min_interruption_words=5,  # Very high - system won't auto-commit interruptions
        resume_false_interruption=False,

    )

    

    
    
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent):
        nonlocal agent_flag
        t = ev.transcript
        is_final = ev.is_final

        logger.info(
            f"{'FINAL' if is_final else 'INTERIM'} transcript: '{t}' (agent_is_speaking={agent_flag})"
        )
        
        if not is_final and agent_flag:
            should_interruptt = should_interrupt(t)
            
            if should_interruptt:
                logger.info(f"Interrupted transcript: '{t}'")
                session.interrupt()
            else:
                logger.info(f"Ignored")
        elif is_final:
            logger.info(f"Final transcript: '{t}'")


    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: AgentStateChangedEvent):
        nonlocal agent_flag
        logger.info(f"Agent state: {ev.old_state} → {ev.new_state}")
        if ev.new_state == "thinking":
            agent_flag = True
            logger.info("Agent speaking = True")

        elif ev.new_state in ("idle", "listening"):
            agent_flag = False
            logger.info("Agent speaking = False")
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
