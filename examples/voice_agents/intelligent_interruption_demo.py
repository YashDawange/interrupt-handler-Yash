"""
Intelligent Interruption Handling Demo

This example demonstrates the intelligent backchanneling filter that allows
the agent to continue speaking when the user provides passive acknowledgements
like "yeah", "ok", "hmm" while the agent is speaking, but still allows real
interruptions like "stop", "wait", or meaningful content.

Test Scenarios:
1. Agent speaking + User says "yeah" -> Agent continues (IGNORE)
2. Agent speaking + User says "wait" -> Agent stops (INTERRUPT)
3. Agent speaking + User says "yeah wait" -> Agent stops (INTERRUPT - mixed input)
4. Agent silent + User says "yeah" -> Agent responds (RESPOND)
"""

import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("intelligent-interruption-demo")

load_dotenv()


class DemoAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You are demonstrating intelligent interruption handling. "
                "When the user says 'tell me a story', tell them a long story about space exploration. "
                "When the user says 'count to ten', count slowly from 1 to 10. "
                "Keep your responses concise otherwise. "
                "Do not use emojis or special characters in your responses."
            ),
        )

    async def on_enter(self):
        # Greet the user and explain what they can test
        self.session.generate_reply(
            instructions=(
                "Greet the user and explain that they can test the intelligent interruption handling. "
                "Tell them to try saying 'tell me a story' and then say 'yeah' or 'ok' while you're talking "
                "to see that you won't stop. But if they say 'wait' or 'stop', you will stop immediately."
            )
        )

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.

        Args:
            location: The location they are asking for
            latitude: The latitude of the location
            longitude: The longitude of the location
        """
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."


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

        # INTELLIGENT INTERRUPTION HANDLING CONFIGURATION
        # Enable backchanneling filter (default: True)
        filter_backchanneling=True,

        # Customize backchanneling words (optional)
        # If not provided, uses default set: {"yeah", "yep", "yes", "ok", "okay",
        # "hmm", "mm", "mhm", "uh-huh", "right", "sure", "alright", "got it", "i see"}
        # backchanneling_words={"yeah", "ok", "hmm", "uh-huh"},

        # Disable false interruption resume since we're handling it intelligently
        resume_false_interruption=False,
    )

    # Log metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(agent=DemoAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
