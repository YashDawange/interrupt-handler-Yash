"""
Demo: Smart interruption handling

This agent won't stop talking when you say "yeah" or "ok" while it's speaking,
but will stop if you say "wait" or "stop".
"""

import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    InterruptionConfig,
    JobContext,
    JobProcess,
    cli,
    function_tool,
)
from livekit.agents.llm import RunContext
from livekit.plugins import deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("intelligent-interruption-demo")
load_dotenv()


class SmartAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You're a friendly AI assistant. When talking, take your time and "
                "explain things clearly. Don't use emojis or markdown formatting."
            ),
        )

    async def on_enter(self):
        self.session.say(
            "Hey! I'm testing smart interruption handling. Try saying 'yeah' or 'ok' "
            "while I'm talking - I won't stop. But say 'wait' and I will."
        )

    @function_tool
    async def tell_story(self, context: RunContext):
        """Tell a story so user can test saying 'yeah' without interrupting."""
        logger.info("Telling story")
        return (
            "So there was this AI that learned to understand the difference between "
            "someone just showing they're listening versus actually wanting to interrupt. "
            "It noticed that humans say things like 'yeah' or 'uh-huh' to show they're "
            "engaged in the conversation, but they don't actually want you to stop. "
            "On the other hand, words like 'wait' or 'stop' are clear signals that "
            "something needs attention. Pretty cool, right?"
        )

    @function_tool
    async def count_slowly(self, context: RunContext):
        """Count numbers so user can test interrupting."""
        logger.info("Counting")
        return "One, two, three, four, five, six, seven, eight, nine, ten."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    
    # Set up smart interruption handling
    interruption_cfg = InterruptionConfig(
        ignore_words=["yeah", "ok", "okay", "hmm", "uh-huh", "mhm", "right", "gotcha"],
        case_sensitive=False,
        enabled=True
    )
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        interruption_config=interruption_cfg,
    )

    await session.start(agent=SmartAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
