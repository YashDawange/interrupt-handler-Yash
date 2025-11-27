"""
Intelligent Interruption Handling Demo Agent

This example demonstrates the intelligent interruption handling feature that
distinguishes between backchannel feedback (like "yeah", "ok", "hmm") and
actual interruptions.

Test Scenarios:
1. Agent is speaking + user says "yeah" → Agent continues (ignored)
2. Agent is speaking + user says "stop" → Agent stops (interrupted)
3. Agent is silent + user says "yeah" → Agent responds (valid input)
4. Agent is speaking + user says "yeah wait" → Agent stops (contains command)
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
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("intelligent-interruption-demo")

load_dotenv()


class DemoAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a demo agent testing intelligent interruption handling. "
                "Your name is Demo Bot. "
                "When asked to explain something, provide a LONG explanation that takes "
                "at least 15-20 seconds to complete. This gives the user time to test "
                "backchannel feedback. "
                "For example, if asked to explain something, give detailed step-by-step "
                "explanations with multiple sentences."
            ),
        )

    async def on_enter(self):
        # Generate a long explanation to demonstrate the interruption handling
        self.session.generate_reply(
            instructions=(
                "Greet the user and explain that you're a demo agent for testing "
                "intelligent interruption handling. "
                "Then, WITHOUT WAITING FOR A RESPONSE, immediately start explaining "
                "how the system works in great detail. "
                "Say something like: 'Let me explain how this works in detail. First... second... third...' "
                "Make your explanation at least 15-20 seconds long so the user can test "
                "saying 'yeah', 'hmm', or 'stop' while you're talking."
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

    # Configure the session with custom backchannel words
    # You can customize this list based on your needs
    custom_backchannel_words = [
        "yeah",
        "ok",
        "okay",
        "hmm",
        "mm-hmm",
        "uh-huh",
        "right",
        "aha",
        "ah",
        "mhm",
        "yep",
        "yup",
        "sure",
        "gotcha",
        "alright",
    ]

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        # NEW: Configure backchannel words for intelligent interruption handling
        backchannel_words=custom_backchannel_words,
    )

    await session.start(
        agent=DemoAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)
