import logging
from time import monotonic
from typing import Optional

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobRequest,
    RoomIO,
    cli,
    AgentStateChangedEvent,
)
from livekit.agents.llm import ChatContext, ChatMessage, StopResponse
from livekit.plugins import cartesia, deepgram, openai

from livekit.agents.interrupt_handler import InterruptHandler

logger = logging.getLogger("intelligent-interrupt")
logger.setLevel(logging.INFO)

load_dotenv()

# --- interruption / backchannel logic ---
interrupt_handler = InterruptHandler()

_agent_state: str = "idle"
_agent_is_speaking: bool = False
_last_speaking_end_ts: Optional[float] = None


class MyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a helpful detailed assistant.",
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o-mini"),
            tts=cartesia.TTS(),
        )

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ):
        global _agent_is_speaking, _last_speaking_end_ts

        text = (new_message.text_content or "").strip()
        if not text:
            raise StopResponse()

        decision = interrupt_handler.classify(text)
        now = monotonic()

        recently_speaking = _agent_is_speaking or (
            _last_speaking_end_ts is not None
            and (now - _last_speaking_end_ts) < 1.0
        )

        logger.info(
            f"user_turn_completed text={text!r}, decision={decision}, "
            f"state={_agent_state}, isSpeaking={_agent_is_speaking}, "
            f"recent={recently_speaking}"
        )

        # Filler while agent is or was just speaking → ignore
        if decision == "FILLER" and recently_speaking:
            logger.info("ignored filler during/after speech")
            raise StopResponse()

        # Otherwise normal generation


async def handle_request(request: JobRequest):
    await request.accept(identity="intelligent-interrupt-agent")


server = AgentServer()


@server.rtc_session(on_request=handle_request)
async def entrypoint(ctx: JobContext):
    global _agent_is_speaking, _last_speaking_end_ts, _agent_state

    # *** CRITICAL FIX ***
    # Connect to room (required for rtc_session workers)
    await ctx.connect()

    session = AgentSession()
    room_io = RoomIO(session, room=ctx.room)
    await room_io.start()

    @session.on("agent_state_changed")
    def _agent_state_event(ev: AgentStateChangedEvent):
        global _agent_is_speaking, _last_speaking_end_ts, _agent_state

        _agent_state = ev.new_state
        logger.info(f"agent_state_changed → {ev.new_state}")

        if ev.new_state == "speaking":
            _agent_is_speaking = True
        else:
            if _agent_is_speaking:
                _last_speaking_end_ts = monotonic()
            _agent_is_speaking = False

    agent = MyAgent()
    await session.start(agent=agent)


if __name__ == "__main__":
    cli.run_app(server)
