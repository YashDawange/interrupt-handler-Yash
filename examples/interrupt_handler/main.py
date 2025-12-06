from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    UserInputTranscribedEvent,
    AgentStateChangedEvent,
)
from livekit.plugins import deepgram, elevenlabs, openai, silero

from .interrupt_handler import AgentStateTracker, handle_transcript


class InterruptAssistant(Agent):
    async def on_enter(self) -> None:
        await self.session.say(
            "Hi, I am an interruption-aware assistant. Ask me anything.",
            allow_interruptions=False,
        )


async def entrypoint(ctx: JobContext) -> None:
    load_dotenv()
    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=elevenlabs.TTS(),
        # Core requirement: VAD cannot auto-interrupt speech
        allow_interruptions=False,
    )

    assistant = InterruptAssistant()
    state = AgentStateTracker()

    @session.on("agent_state_changed")
    def _on_state(ev: AgentStateChangedEvent) -> None:
        state.update_from_event(ev)

    @session.on("user_input_transcribed")
    def _on_transcribed(ev: UserInputTranscribedEvent) -> None:
        handle_transcript(ev, session=session, state=state)

    await session.start(agent=assistant, room=ctx.room)
    await session.wait_closed()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
