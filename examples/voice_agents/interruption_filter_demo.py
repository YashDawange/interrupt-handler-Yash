"""
Example agent demonstrating the intelligent interruption filter.

This agent showcases how the interruption filter distinguishes between:
1. Passive acknowledgements ("yeah", "ok", "hmm") - ignored when agent is speaking
2. Active interruptions ("wait", "stop", "no") - always interrupt the agent
3. Valid input when agent is silent - processed normally

Test scenarios:
- While agent is speaking, say "yeah" or "ok" - agent should continue speaking
- While agent is speaking, say "wait" or "stop" - agent should interrupt immediately
- When agent is silent, say "yeah" - agent should respond normally
- While agent is speaking, say "yeah wait" - agent should interrupt (contains command)
"""

import logging
import os
import sys

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    cli,
    room_io,
)
from livekit.plugins import silero

logger = logging.getLogger("interruption-filter-demo")

# Enable debug logging to capture filter decisions for proof
# Set LIVEKIT_DEBUG=true environment variable to enable
if os.environ.get("LIVEKIT_DEBUG", "").lower() == "true":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler('interruption_filter_proof.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.getLogger("livekit.agents.voice.agent_activity").setLevel(logging.DEBUG)
    logger.info("Debug logging enabled - logs saved to interruption_filter_proof.log")

load_dotenv()


class InterruptionFilterDemoAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful assistant demonstrating intelligent interruption handling. "
                "When speaking, you should provide detailed explanations that take some time. "
                "For example, explain the history of artificial intelligence, or describe how "
                "voice agents work in detail. Keep your responses informative and engaging. "
                "Do not use emojis, asterisks, markdown, or other special characters."
            )
        )

    async def on_enter(self):
        # Start with a greeting and explanation
        self.session.generate_reply(
            instructions=(
                "Greet the user and explain that you're demonstrating intelligent interruption handling. "
                "Tell them they can say 'yeah' or 'ok' while you're speaking and you'll continue, "
                "or say 'wait' or 'stop' to interrupt you. Then ask if they're ready to begin."
            )
        )


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(),
        # The interruption filter is enabled by default
        # You can configure it via environment variables:
        # LIVEKIT_INTERRUPTION_FILTER_ENABLED=true (default: true)
        # LIVEKIT_PASSIVE_WORDS=yeah,ok,hmm,right,uh-huh (comma-separated)
        # LIVEKIT_INTERRUPT_WORDS=wait,stop,no,hold on (comma-separated)
        allow_interruptions=True,
        resume_false_interruption=True,
        false_interruption_timeout=2.0,
    )

    await session.start(
        agent=InterruptionFilterDemoAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(entrypoint)