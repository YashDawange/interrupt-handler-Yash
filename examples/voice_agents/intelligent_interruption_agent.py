"""Example agent demonstrating intelligent interruption handling.

This agent demonstrates how the intelligent interruption handler works:
- When the agent is speaking and the user says backchanneling words like
  "yeah", "ok", "hmm", the agent continues speaking without interruption
- When the user says interruption commands like "wait", "stop", "no",
  the agent stops immediately
- When the agent is silent and the user says "yeah" or "ok", the agent
  responds normally (treats it as valid input)

To test:
1. Start the agent and let it speak
2. While it's speaking, say "yeah" or "ok" - it should continue
3. While it's speaking, say "wait" or "stop" - it should stop
4. When the agent asks a question and goes silent, say "yeah" - it should respond
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.plugins import openai, silero

logger = logging.getLogger("intelligent-interruption-agent")

# Load .env from repository root (2 levels up from this file)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class IntelligentInterruptionAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful assistant named Alex. "
                "You are explaining things to users in a conversational way. "
                "When explaining something, speak naturally and at a moderate pace. "
                "Keep your responses concise but informative. "
                "Do not use emojis, asterisks, markdown, or other special characters. "
                "You are friendly and patient."
            ),
        )

    async def on_enter(self):
        # Start with a greeting and a long explanation to test interruption handling
        self.session.generate_reply(
            instructions=(
                "Greet the user and then explain a topic of your choice in detail. "
                "For example, explain how photosynthesis works, or describe the history "
                "of the internet, or explain how computers work. "
                "Speak for at least 30 seconds to give the user time to test interruptions."
            )
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Configure the session with intelligent interruption handling enabled
    # The interruption handler is automatically enabled and uses default settings
    # You can customize it via environment variables:
    # - LIVEKIT_AGENT_IGNORE_WORDS: comma-separated list of words to ignore
    # - LIVEKIT_AGENT_INTERRUPTION_COMMANDS: comma-separated list of interruption commands
    session = AgentSession(
        # Using OpenAI for all services (STT, LLM, TTS) - only requires OPENAI_API_KEY
        stt=openai.STT(model="whisper-1"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(model="tts-1", voice="nova"),
        vad=ctx.proc.userdata["vad"],
        # Enable false interruption resume to handle edge cases
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        # Allow preemptive generation for better responsiveness
        preemptive_generation=True,
    )

    await session.start(
        agent=IntelligentInterruptionAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)

