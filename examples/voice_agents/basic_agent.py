import logging
import asyncio
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
from interruption_handle import InterruptionLogic


import string
from livekit.agents.voice.agent_activity import AgentActivity

PATCH_LOGGER = logging.getLogger("backchannel-patch")

IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "aha",
    "right", "sure", "yep", "yes",
    "uh-huh", "uhuh", "continue", "go", "on"
}

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)

def _is_pure_backchannel(text: str) -> bool:
    clean = text.lower().translate(_PUNCT_TABLE)
    words = clean.split()
    return bool(words) and all(w in IGNORE_WORDS for w in words)

_original_on_final = AgentActivity.on_final_transcript

def patched_on_final_transcript(self, ev, *, speaking=None):
    try:
        transcript = ev.alternatives[0].text
    except Exception:
        return _original_on_final(self, ev, speaking=speaking)

    if self._session.agent_state == "speaking":
        if _is_pure_backchannel(transcript):
            PATCH_LOGGER.info(
                f"IGNORING BACKCHANNEL (no pause, no interrupt): '{transcript}'"
            )
            return 
    # Otherwise → normal LiveKit behavior
    return _original_on_final(self, ev, speaking=speaking)

# Apply patch 
AgentActivity.on_final_transcript = patched_on_final_transcript

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
        pass
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
        turn_detection="vad",
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=False,
        # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
        # when it's detected, you may resume the agent's speech
        resume_false_interruption=True,
        false_interruption_timeout=0.3,
    )
    logic = InterruptionLogic()


    def _on_user_input(ev):
        if ev.is_final:
            asyncio.create_task(handle_user_input(ev))


    async def handle_user_input(ev):
        text = ev.transcript.strip()
        if not text:
            return

        decision = logic.decide(text)

        if decision == "IGNORE":
            logger.info(f"Filtered backchannel: '{text}'")
            return

        if decision == "INTERRUPT":
            logger.info(f"User interruption intent: '{text}'")
            return  # LiveKit handles interruption internally

        # NORMAL TURN
        await session.generate_reply()


    session.on("user_input_transcribed", _on_user_input)




    
    # logic = InterruptionLogic()


    # # @session.on("agent_state_changed")
    # # def _on_agent_state(ev): 
    # #     logic.update_agent_state(ev.new_state)
    
    # # @session.on("user_state_changed")
    # # def _on_user_state(ev):
    # #     if ev.new_state== "speaking" and logic.agent_is_speaking: 
    # #         logic.mark_vad_detected()
    

    # def _on_user_input(ev):
    #     asyncio.create_task(handle_user_input(ev))


    # async def handle_user_input(ev):
    #     if not ev.is_final:
    #         return

    #     text = ev.transcript.strip()
    #     if not text:
    #         return

    #     decision = logic.decide(text)

    #     # Ignore backchannels completely
    #     if decision == "IGNORE":
    #         logger.debug(f"Ignoring backchannel: {text}")
    #         return

    #     # Real interruption intent → LiveKit already handles it
    #     if decision == "INTERRUPT":
    #         logger.info(f"User interruption intent: {text}")
    #         return

    #     # Normal conversational response
    #     await session.generate_reply()

        



    # session.on("user_input_transcribed", _on_user_input)


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
