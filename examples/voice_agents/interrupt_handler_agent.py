import sys
import os

# Ensure repo root is on PYTHONPATH (required for LiveKit workers)
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../")
)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import logging
import re
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    llm,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from config.interrupt_policy import IGNORE_WORDS, INTERRUPT_WORDS

load_dotenv()
logger = logging.getLogger("interrupt-handler")
logger.setLevel(logging.INFO)


# -------------------------------------------------
# Agent speaking state
# -------------------------------------------------

class AgentState:
    is_speaking = False

agent_state = AgentState()

# -------------------------------------------------
# Helpers
# -------------------------------------------------

def normalize(text: str) -> set[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return set(text.split())

# -------------------------------------------------
# Intelligent Turn Detector
# -------------------------------------------------

class IntelligentTurnDetector(MultilingualModel):
    async def predict_end_of_turn(self, chat_ctx: llm.ChatContext) -> float:
        last_user = None
        for item in reversed(chat_ctx.items):
            if item.type == "message" and item.role == "user":
                last_user = item.text_content
                break

        if not last_user:
            return 1.0

        words = normalize(last_user)

        has_interrupt = bool(words & INTERRUPT_WORDS)
        is_ignore_only = bool(words) and words.issubset(IGNORE_WORDS)

        logger.info(
            f"TurnDetector | '{last_user}' | "
            f"ignore_only={is_ignore_only} interrupt={has_interrupt} "
            f"speaking={agent_state.is_speaking}"
        )

        if agent_state.is_speaking:
            # Backchannel → false interruption
            if is_ignore_only and not has_interrupt:
                return 0.0

            # Real or mixed input → interrupt
            return 1.0

        # Agent silent → normal behavior
        return 1.0

# -------------------------------------------------
# Agent
# -------------------------------------------------

class InterruptHandlerAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "Your name is Kelly. You are a friendly assistant. "
                "When users say short acknowledgements like 'yeah' or 'ok' while you are speaking, "
                "they are just listening — continue naturally."
            )
        )

    async def on_enter(self):
        self.session.generate_reply()

# -------------------------------------------------
# Server
# -------------------------------------------------

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

# -------------------------------------------------
# Entrypoint
# -------------------------------------------------

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=ctx.proc.userdata["vad"],

        allow_interruptions=True,
        resume_false_interruption=True,   # 🔑 handles false-start VAD
        preemptive_generation=True,

        turn_detection=IntelligentTurnDetector(),
    )

    @session.on("agent_state_changed")
    def on_state(event):
        agent_state.is_speaking = (event.new_state == "speaking")

    await session.start(
        agent=InterruptHandlerAgent(),
        room=ctx.room,
    )

# -------------------------------------------------

if __name__ == "__main__":
    cli.run_app(server)
