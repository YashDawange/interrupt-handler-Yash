"""Demo of agent showcasing intelligent interruption handling."""

import logging
from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, JobProcess, cli
from livekit.agents.worker import AgentServer
from livekit.plugins import silero, deepgram, cartesia, groq

logger = logging.getLogger("demo-interruption")
logger.setLevel(logging.INFO)
load_dotenv()


class InterruptionDemoAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful voice assistant. When explaining topics, provide detailed, "
                "thoughtful responses that take 15-20 seconds to complete. Speak naturally and "
                "at a conversational pace. If interrupted, respond appropriately to what the user said."
            )
        )
    
    async def on_enter(self):
        """Greet the user when they join."""
        await self.session.generate_reply(
            instructions="Say: Hello! I'm your voice assistant. Feel free to ask me anything and I'll explain in detail."
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    """Preload the VAD model."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Entry point for each new session."""
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=groq.LLM(model="llama-3.1-8b-instant"),
        tts=cartesia.TTS(),
        vad=ctx.proc.userdata["vad"],
        turn_detection="vad",
        
        # Interruption settings for testing
        allow_interruptions=True,
        resume_false_interruption=True,
        false_interruption_timeout=0.5,
    )
    
    await session.start(agent=InterruptionDemoAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)