"""
Example agent demonstrating Intelligent Interruption Handling

This agent showcases the intelligent interruption handling feature that distinguishes
between passive acknowledgements (backchanneling) and active interruptions.

The agent will:
- Continue speaking when user says "yeah", "ok", "hmm" while agent is speaking
- Stop immediately when user says "wait", "stop", "no" while agent is speaking
- Respond normally to "yeah", "ok" when agent is silent
- Handle mixed inputs like "yeah wait" correctly (interrupts because of "wait")

To test:
1. Start the agent: python examples/voice_agents/intelligent_interruption_agent.py dev
2. Connect using LiveKit client or playground
3. Try these scenarios:
   - While agent is speaking, say "yeah" or "ok" - agent should continue
   - While agent is speaking, say "stop" or "wait" - agent should stop
   - When agent asks a question and is silent, say "yeah" - agent should respond
   - While agent is speaking, say "yeah wait" - agent should stop (mixed input)
"""

import logging
import os

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

logger = logging.getLogger("intelligent-interruption-agent")

load_dotenv()


class IntelligentInterruptionAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful assistant named Alex. "
                "You are explaining things to users in a conversational way. "
                "When explaining something, be thorough and detailed. "
                "Keep your responses natural and engaging. "
                "Do not use emojis, asterisks, markdown, or other special characters. "
                "You speak English to the user."
            )
        )

    async def on_enter(self):
        # Greet the user and start a conversation
        self.session.generate_reply(
            instructions=(
                "Greet the user warmly and ask if they'd like to hear "
                "an interesting fact about history or science. "
                "Wait for their response."
            )
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    """Preload VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Configure the agent session with intelligent interruption handling
    # The interruption handler is automatically enabled by default
    # You can configure it via environment variables:
    # - LIVEKIT_AGENTS_INTELLIGENT_INTERRUPTION=true (default: true)
    # - LIVEKIT_AGENTS_BACKCHANNEL_WORDS=yeah,ok,hmm,right (comma-separated)
    # - LIVEKIT_AGENTS_INTERRUPT_COMMANDS=wait,stop,no (comma-separated)

    session = AgentSession(
        # Speech-to-text
        stt="deepgram/nova-3",
        # Large Language Model
        llm="openai/gpt-4o-mini",
        # Text-to-speech
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # Voice Activity Detection
        vad=ctx.proc.userdata["vad"],
        # Turn detection
        turn_detection="vad",
        # Allow interruptions (required for intelligent interruption handling)
        allow_interruptions=True,
        # Resume false interruptions (when user makes noise but doesn't actually speak)
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        # Preemptive generation for lower latency
        preemptive_generation=True,
    )

    # Log when agent state changes (useful for debugging)
    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        logger.info(f"Agent state: {ev.old_state} -> {ev.new_state}")

    @session.on("user_state_changed")
    def _on_user_state_changed(ev):
        logger.info(f"User state: {ev.old_state} -> {ev.new_state}")

    await session.start(
        agent=IntelligentInterruptionAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)

