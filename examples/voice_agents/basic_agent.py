import logging
import os
import re  # <-- add this

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
    AgentStateChangedEvent,      # added this
    UserInputTranscribedEvent,   # added this
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

        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."




# Interrupt / backchannel logic helper

class InterruptHandler:
    def __init__(self) -> None:
        ignore_words = os.getenv(
            "INTERRUPT_IGNORE_WORDS",
            "yeah,ok,okay,kk,hmm,huh,right,uh,uhh,uhm,umm,uhhuh,uh-huh,mm,mmhmm,mm-hmm,mhm,sure,alright,go,continue,good,fine,indeed,correct,yep,yup,gotcha,gotit,alrighty,okayokay,yeahyeah",
        )
        interrupt_words = os.getenv(
            "INTERRUPT_COMMAND_WORDS",
            "stop,wait,no,cancel,enough,hold,just,second,minute,moment,sorry,interrupt,pause,hang,wrong,stopper,holdon,stopit,dont,clarify",
        )


        self.ignore_tokens = {w.strip().lower() for w in ignore_words.split(",") if w.strip()}
        self.command_tokens = {w.strip().lower() for w in interrupt_words.split(",") if w.strip()}

    def _tokenize(self, text: str) -> list[str]:
        # basic word tokenizer
        return re.findall(r"[a-z']+", text.lower())

    def classify(self, text: str, agent_is_speaking: bool) -> str:
        """
        Returns one of: "ignore", "interrupt", "respond"
        """
        tokens = self._tokenize(text)
        if not tokens:
            return "respond"

        has_command = any(t in self.command_tokens for t in tokens)
        soft_only = all(t in self.ignore_tokens for t in tokens)

        # ANY command word means interrupt, regardless of speaking state
        if has_command:
            return "interrupt"

        # Only ignore soft fillers while the agent is speaking
        if agent_is_speaking and soft_only:
            return "ignore"

        # Everything else is normal conversational input
        return "respond"








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
        resume_false_interruption=False,
        false_interruption_timeout=1.0,
        # IMPORTANT: we will control interruptions ourselves
        allow_interruptions=False,                # don't let default VAD interrupt
        discard_audio_if_uninterruptible=False,   # BUT still send audio to STT so we can see "stop/yeah/..."
        # (optional) these are mainly for default interruptions, but safe to set:
        # min_interruption_duration=0.0,
        # min_interruption_words=1,
    )


    interrupt_handler = InterruptHandler()
    agent_state = {"is_speaking": False}

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        # new_state is a string like "speaking", "listening", "thinking"
        agent_state["is_speaking"] = ev.new_state == "speaking"
        logger.info(f"Agent state changed: {ev.old_state} -> {ev.new_state}")


    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        text = (ev.transcript or "").strip()
        if not text:
            return

        speaking = agent_state["is_speaking"]
        action = interrupt_handler.classify(text, speaking)

        logger.info(
            f"Transcript: '{text}' (final={ev.is_final}) "
            f"→ {action} (speaking={speaking})"
        )

        if action == "interrupt":
            # HARD STOP: no matter what the state says, user clearly wants to cut
            logger.info("Interrupting agent due to command word.")
            session.interrupt(force=True)
            # Also clear the current user turn so we don't respond to "stop" as a question
            session.clear_user_turn()
            return

        if speaking and action == "ignore":
            # Backchannel while speaking – only clear once on final transcript
            if ev.is_final:
                session.clear_user_turn()
                logger.info("Ignoring backchannel while speaking (final).")
            return

        # If agent is silent or action == "respond", let it flow as normal input
        if not ev.is_final:
            # avoid spamming LLM with partials when listening
            return

        logger.info("Agent silent or normal input → letting transcript flow normally.")
        # Do nothing else here: the standard pipeline will handle the user turn.






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
