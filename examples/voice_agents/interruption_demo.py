"""
Intelligent Interruption Demo Agent

This example demonstrates the intelligent interruption filtering capability.
The agent will:
1. Continue speaking when users say filler words (yeah, ok, hmm)
2. Stop immediately when users say command words (wait, stop, no)
3. Stop for mixed input containing commands
4. Respond normally to filler words when the agent is silent
"""

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

logger = logging.getLogger("interruption-demo")
logger.setLevel(logging.INFO)

load_dotenv()


class DemoAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Alex, an AI assistant demonstrating intelligent interruption handling. "
                "You will speak naturally and at a moderate pace. "
                "When explaining something, take your time and provide detailed information. "
                "If a user says 'yeah', 'ok', or 'hmm' while you're speaking, continue seamlessly without pausing. "
                "If they say 'wait', 'stop', or 'no', stop immediately and listen to their request. "
                "Keep responses conversational and friendly."
            ),
        )

    async def on_enter(self):
        # Generate a greeting that will allow testing interruption behavior
        self.session.say(
            "Hello! I'm Alex, your AI assistant. Let me tell you about how our new intelligent "
            "interruption system works. It can distinguish between when you're just acknowledging "
            "what I'm saying with words like 'yeah' or 'okay', versus when you actually want me "
            "to stop with words like 'wait' or 'stop'. This makes our conversation feel much more "
            "natural and human-like. Feel free to try interrupting me with different phrases to "
            "see how it responds!"
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm the VAD model to reduce startup latency"""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entrypoint for the agent session"""
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        # Speech-to-text for transcribing user speech
        stt="deepgram/nova-3",
        # LLM for generating responses
        llm="openai/gpt-4o-mini",
        # Text-to-speech for agent voice
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # VAD for detecting when user starts/stops speaking
        vad=ctx.proc.userdata["vad"],
        # Enable turn detection
        turn_detection="vad",
        # Allow interruptions (the filter will decide when to actually interrupt)
        allow_interruptions=True,
        # Enable preemptive generation for faster responses
        preemptive_generation=True,
        # Enable false interruption detection and resume
        resume_false_interruption=True,
        false_interruption_timeout=1.5,
    )

    await session.start(
        agent=DemoAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)
