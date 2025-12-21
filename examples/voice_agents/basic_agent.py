import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AgentStateChangedEvent,
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
from livekit.plugins import silero

# make local modules importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from interrupt_handler import IGNORE_SET, INTERRUPT_SET, START_SET
from interrupt_handler.intent_controller import IntentClassifier
from interrupt_handler.interruption_policy import ContextAwarePolicy, Action
from interrupt_handler.voice_interrupt_controller import ContextAwareVoiceController

logger = logging.getLogger("basic-agent")
load_dotenv()


# =========================
# AGENT DEFINITION
# =========================

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Keep responses concise and to the point. "
                "Do not use emojis, markdown, or special characters. "
                "You are curious, friendly, and slightly humorous. "
                "You speak English."
            )
        )

    async def on_enter(self):
        self.session.generate_reply()

    # @function_tool
    # async def lookup_weather(
    #     self, context: RunContext, location: str, latitude: str, longitude: str
    # ):
    #     logger.info(f"Looking up weather for {location}")
    #     return "sunny with a temperature of 70 degrees."



# SERVER SETUP


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


# SESSION ENTRYPOINT
@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    # -------------------------
    # Context-aware interrupt controller
    # -------------------------
    interrupt_controller = ContextAwareVoiceController(
        classifier=IntentClassifier(
            backchannel_words=IGNORE_SET,
            interrupt_words=INTERRUPT_SET,
            start_words=START_SET,
        ),
        policy=ContextAwarePolicy(),
    )

    logger.info("Context-aware interrupt controller initialized")

    # -------------------------
    # Agent session
    # -------------------------
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="google/gemini-2.5-flash",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection="vad",
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        min_interruption_words=2,
        min_interruption_duration=0.6,
        false_interruption_timeout=None,
        resume_false_interruption=False,
    )

    # -------------------------
    # EVENT HANDLERS
    # -------------------------

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        interrupt_controller.update_agent_state(ev.new_state)
        logger.debug(f"Agent state: {ev.old_state} -> {ev.new_state}")

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        transcript = ev.transcript.strip()
        if not transcript:
            return

        # fast-path for interim transcripts
        if not ev.is_final:
            quick = transcript.lower().replace("-", " ")
            if any(w in quick for w in {"stop", "wait", "pause", "hold"}):
               session.interrupt()
               session.clear_user_turn()
               return

        action = interrupt_controller.handle_transcript(
            transcript=transcript,
            is_final=ev.is_final,
        )

        if action == Action.IGNORE:
            if ev.is_final:
                session.clear_user_turn()
                logger.info(f"IGNORED backchannel: '{transcript}'")

        elif action == Action.INTERRUPT:
            session.interrupt()
            session.clear_user_turn()
            logger.info(f"INTERRUPTED by user: '{transcript}'")

        # Action.PASS -> let LiveKit handle normally

    # -------------------------
    # METRICS
    # -------------------------

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Session usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # -------------------------
    # START SESSION
    # -------------------------

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions()
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
