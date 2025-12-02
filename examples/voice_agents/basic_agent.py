import logging
import os
import sys

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
from livekit.agents.llm import StopResponse
from livekit.agents.llm import ChatContext, ChatMessage 

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation
# --- make repo root importable so we can import interrupt_handler.py from root ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))  # go up two levels: .../agents-assignment
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


from interrupt_handler import InterruptHandler, InterruptionType  # 👈 our logic layer

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


    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """
        Called when the user finishes speaking and STT has produced text.
        We decide here whether to ignore, interrupt, or treat as normal input.
        """
        # Handle both: new_message may be a str or an object
        if isinstance(new_message, str):
            text = new_message.strip()
        else:
            if hasattr(new_message, "text_content"):
                tc = new_message.text_content
                text = (tc() if callable(tc) else tc) or ""
            elif hasattr(new_message, "text"):
                t = new_message.text
                text = (t() if callable(t) else t) or ""
            else:
                text = str(new_message or "")
            text = text.strip()

        logger.debug(f"User turn completed with text: {text!r}")

        handler: InterruptHandler | None = self.session.userdata.get("interrupt_handler")
        interrupt_state = self.session.userdata.get("interrupt_state") or {}

        current_state = interrupt_state.get("agent_state")
        interrupted_speech = bool(interrupt_state.get("interrupted_speech", False))

        # consider this utterance as coming "during speech" if
        # we either are still speaking OR we were just interrupted from speaking
        agent_was_speaking = (current_state == "speaking") or interrupted_speech

        if handler is None:
            return await super().on_user_turn_completed(turn_ctx, new_message)

        kind = handler.classify(text, agent_is_speaking=agent_was_speaking)
        logger.debug(
            f"Interruption classification: {kind} "
            f"(current_state={current_state}, interrupted_speech={interrupted_speech})"
        )

        # whatever happens, this user turn "consumes" the interruption flag
        interrupt_state["interrupted_speech"] = False

        # 1) Agent was speaking + passive ack ("yeah/ok/hmm") => IGNORE this turn
        if kind == InterruptionType.PASSIVE_ACK and agent_was_speaking:
            logger.info(
                "Ignoring passive acknowledgement while speaking: %r", text
            )
            logger.debug("Raising StopResponse() to cancel reply for passive ack")
            # abort STT → LLM → TTS for this user turn
            raise StopResponse()

        # 2) Active interrupt ("stop/no/wait") => let normal flow handle it
        if kind == InterruptionType.ACTIVE_INTERRUPT:
            logger.info(f"Active interruption from user: {text!r}")
            return await super().on_user_turn_completed(turn_ctx, new_message)

        # 3) NONE (or PASSIVE_ACK when agent was *not* speaking) => normal behavior
        return await super().on_user_turn_completed(turn_ctx, new_message)



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

    # --- interruption handling state & config (create BEFORE session) ---
    interrupt_state = {
        "agent_state": "initializing",
        "interrupted_speech": False,  # becomes True when speaking is cut by user
    }

    interrupt_handler = InterruptHandler(
        passive_ack_words=["yeah", "ok", "okay", "hmm", "uh-huh", "uh huh", "right"],
        interrupt_words=["stop", "wait", "no", "hold on", "hang on"],
    )

    user_data = {
        "interrupt_state": interrupt_state,
        "interrupt_handler": interrupt_handler,
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
        # 🔑 this initializes session.userdata properly
        userdata=user_data,
    )

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        # track current state
        previous_state = interrupt_state.get("agent_state")
        interrupt_state["agent_state"] = ev.new_state

        # If we were speaking and now we are not, this was likely a barge-in.
        if previous_state == "speaking" and ev.new_state in ("listening", "thinking"):
            interrupt_state["interrupted_speech"] = True
            logger.debug("Speech interrupted by user input")
        elif ev.new_state == "speaking":
            # starting a fresh agent turn; clear old interruption flag
            interrupt_state["interrupted_speech"] = False

        logger.debug(f"Agent state: {ev.old_state} -> {ev.new_state}")


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
