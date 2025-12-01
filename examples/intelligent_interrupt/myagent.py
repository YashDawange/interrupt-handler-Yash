import asyncio
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, elevenlabs, openai, silero

from intelligent_interrupt.interrupt_handler import InterruptHandler


class InterruptAwareAgent(Agent):
    """
    Simple agent that will be used to manually test interruption behavior.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a friendly voice assistant. "
                "Explain things clearly, use reasonably long sentences, "
                "and continue speaking unless the user clearly interrupts you."
            )
        )

    async def on_enter(self):
        # Start with a long-ish explanation so we can test backchannels.
        await self.session.generate_reply(
            instructions=(
                "Give a long explanation about a simple topic, such as how the solar system works."
            )
        )


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    agent = InterruptAwareAgent()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=elevenlabs.TTS(),
    )

    # Attach our intelligent interrupt logic layer.
    InterruptHandler(session)

    await session.start(agent=agent, room=ctx.room)

    # Optionally, ask a question after the first explanation to test Scenario 2:
    # Agent: "Are you ready?"
    await session.generate_reply(
        instructions="Ask the user if they are ready to continue."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
