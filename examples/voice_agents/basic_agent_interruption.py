import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    UserInputTranscribedEvent,
    AgentStateChangedEvent,
    WorkerOptions,
    cli,
    metrics,
    RoomInputOptions,
    RoomOutputOptions,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from basic_agent_interruption_handler import (
    InterruptionPolicy,
    InterruptionFilter,
    InterruptionDecision,
)

logger = logging.getLogger("basic-agent")
load_dotenv()


# =========================
# AGENT
# =========================
class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. "
                "You are a conversational AI assistant. "
                "Speak naturally and concisely. "
                "Do not use emojis or markdown."
                "You are NOT limited to any single domain. "
                "You should only use tools when they are clearly useful, "
                "and you should never say that you are incapable of answering general questions. "
                "If a question is abstract or conceptual, explain it in simple terms. "
                "If the user asks about weather, you may use the weather tool. "
            )
        )

    async def on_enter(self):
        # generate an initial reply when agent enters
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self,
        context: RunContext,
        location: str,
        latitude: str,
        longitude: str,
    ):
        return "It is sunny and 70 degrees."


# =========================
# PREWARM
# =========================
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    # store a default policy instance for each worker process
    proc.userdata["interrupt_policy"] = InterruptionPolicy()


# =========================
# ENTRYPOINT
# =========================
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",

        turn_detection=MultilingualModel(),
        # vad=ctx.proc.userdata["vad"],

        preemptive_generation=True,

        # SAME AS PASTED SCRIPT
        allow_interruptions=True,
        discard_audio_if_uninterruptible=True,
        min_interruption_duration=0.6,
        min_interruption_words=2,
    )

    # =========================
    # METRICS
    # =========================
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    ctx.add_shutdown_callback(
        lambda: logger.info(f"Usage: {usage_collector.get_summary()}")
    )

    # =========================
    # AGENT STATE TRACKING
    # =========================
    agent_speaking = {"value": False}

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        agent_speaking["value"] = ev.new_state == "speaking"

    # =========================
    # INTERRUPTION FILTER
    # =========================
    interrupt_filter = InterruptionFilter(ctx.proc.userdata["interrupt_policy"])

    # =========================
    # USER BUFFER (Option 1)
    #   - accumulate all STT segments (interim + final) while agent is speaking
    #   - when a final segment arrives, process the entire accumulated text
    # =========================
    user_buffer = {"text": ""}

    # Helper to flush+decide on buffer
    def _flush_and_handle_buffer():
        full_text = user_buffer["text"].strip()
        user_buffer["text"] = ""  # clear buffer immediately
        if not full_text:
            return

        decision = interrupt_filter.decide(text=full_text, agent_speaking=True)

        if decision == InterruptionDecision.IGNORE:
            # exactly like pasted script
            session.clear_user_turn()
            return

        if decision == InterruptionDecision.INTERRUPT:
            session.interrupt(force=True)
            return

    # =========================
    # USER INPUT HANDLER (with accumulation)
    # =========================
    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        text = (ev.transcript or "").strip()
        if not text:
            return

        # Only care about user speech that happens WHILE agent is speaking.
        # If the agent is not speaking, let the framework handle it normally.
        if not agent_speaking["value"]:
            return

        # Accumulate every STT segment (interim OR final).
        # Many STT streams will emit short early finals while the user is still talking —
        # collecting segments avoids missing words.
        # We add a space only if there's existing buffered text.
        if user_buffer["text"]:
            user_buffer["text"] += " " + text
        else:
            user_buffer["text"] = text

        # Only make a decision when we have a final segment.
        # This ensures we consider the entire utterance the ASR has accumulated.
        if not getattr(ev, "is_final", False):
            return

        # ev.is_final is True -> process accumulated buffer
        _flush_and_handle_buffer()

    # =========================
    # START SESSION
    # =========================
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
