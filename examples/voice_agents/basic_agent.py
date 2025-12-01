import logging
import os
import json
import re
from dataclasses import dataclass, field
from typing import Set

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
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("basic-agent")

load_dotenv()


# ------------------------ INTERRUPTION CONTROLLER ------------------------ #

DEFAULT_SOFT_WORDS = ["yeah", "ok", "okay", "hmm", "uh-huh", "right", "aha"]
DEFAULT_COMMAND_WORDS = ["stop", "wait", "hold", "no", "cancel", "pause"]


def _load_word_list(env_var: str, default: list[str]) -> Set[str]:
    raw = os.getenv(env_var)
    if not raw:
        return set(default)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return {str(w).lower() for w in parsed}
    except Exception:
        pass
    return set(default)


@dataclass
class InterruptController:
    """
    Prevent disruption on soft backchannels (yeah, ok, hmm),
    but interrupt immediately on stop/wait/no, etc.
    """

    session: AgentSession
    soft_words: Set[str] = field(
        default_factory=lambda: _load_word_list("INTERRUPT_SOFT_WORDS", DEFAULT_SOFT_WORDS)
    )
    command_words: Set[str] = field(
        default_factory=lambda: _load_word_list("INTERRUPT_COMMAND_WORDS", DEFAULT_COMMAND_WORDS)
    )

    agent_state: str = "idle"

    def __post_init__(self) -> None:
        @self.session.on("agent_state_changed")
        def _on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
            self.agent_state = ev.new_state

        @self.session.on("user_input_transcribed")
        def _on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
            text = (ev.transcript or "").strip().lower()
            if not text or not ev.is_final:
                return

            # If agent is NOT speaking, allow normal handling
            if self.agent_state != "speaking":
                return

            intent = self._classify_intent(text)
            if intent == "ignore":
                return  # pure backchannel → don't interrupt

            # Manual interruption for real intent or command
            self.session.interrupt()
            self.session.generate_reply(user_input=text)

    def _tokenize(self, text: str) -> list[str]:
        result = []
        for tok in text.split():
            clean = re.sub(r"[^\w'-]", "", tok)
            if clean:
                result.append(clean)
        return result

    def _classify_intent(self, text: str) -> str:
        tokens = [t.lower() for t in self._tokenize(text)]
        if not tokens:
            return "ignore"
        has_command = any(t in self.command_words for t in tokens)
        soft_only = all(t in self.soft_words for t in tokens)
        if has_command:
            return "command"
        if soft_only:
            return "ignore"
        return "interrupt"


# ------------------------------ AGENT LOGIC ------------------------------ #

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You would interact with users via voice. "
                "Keep responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or other special characters. "
                "You are curious and friendly and speak English."
            ),
        )

    async def on_enter(self):
        self.session.generate_reply(instructions="Greet the user.")


@function_tool
async def lookup_weather(
    context: RunContext, location: str, latitude: str, longitude: str
):
    return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,

        # allow interruptions, but make auto-interrupts harder to trigger
        allow_interruptions=True,
        min_interruption_words=3,        # auto interrupt only if user says ≥ 3 words
        min_interruption_duration=0.5,   # and speaks for at least 0.5s
    )

    # attach our interruption handler
    InterruptController(session)

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage: {usage_collector.get_summary()}")

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
