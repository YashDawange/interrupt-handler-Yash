import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("interrupt-test-agent")

load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are a helpful assistant. You are explaining a very long and detailed history of the Roman Empire. You should speak continuously for at least 30 seconds. If interrupted, stop. If the user says 'yeah' or 'ok', continue speaking.",
        )

    async def on_enter(self):
        self.session.generate_reply(instructions="Start explaining the history of the Roman Empire. Make it long.")

server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        ignored_words=["yeah", "ok", "hmm", "right", "uh-huh", "aha"],
    )
    
    agent = MyAgent()
    session.start(room=ctx.room, agent=agent)

if __name__ == "__main__":
    cli.run_app(server)
