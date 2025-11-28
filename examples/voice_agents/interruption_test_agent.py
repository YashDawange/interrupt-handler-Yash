"""
Intelligent Interruption Handling Test Agent

This agent demonstrates and tests the backchanneling feature where the agent
will not stop speaking when users say passive acknowledgments like "yeah", "ok", "hmm".

Test Scenarios:
1. Long Explanation: Agent speaks a long paragraph, user says "yeah", agent continues
2. Passive Affirmation: Agent asks a question and waits, user says "yeah", agent responds
3. Real Interruption: Agent speaks, user says "stop", agent stops immediately
4. Mixed Input: Agent speaks, user says "yeah wait", agent stops (contains non-backchanneling)
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
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
logger = logging.getLogger("interruption-test-agent")

load_dotenv()

class InterruptionTestAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly, a friendly AI assistant designed to test interruption handling. "
                "When asked to tell a long story or explanation, you should speak continuously "
                "for at least 30-45 seconds without pausing. "
                "When you ask questions, wait for the user's response. "
                "Keep your responses clear and natural. "
                "Do not use emojis or special characters. "
                "When telling a story, make it engaging and continuous."
            ),
        )

    async def on_enter(self):
        self.session.generate_reply(
            instructions=(
                "Greet the user warmly and explain that you're a test agent for interruption handling. "
                "Tell them you can demonstrate several scenarios: "
                "1. Tell a long story where they can say 'yeah' or 'ok' and you'll keep talking "
                "2. Ask them questions where 'yeah' will be treated as an answer "
                "3. Show that saying 'stop' or 'wait' will interrupt you immediately. "
                "Ask them which scenario they'd like to try first."
            )
        )

    @function_tool
    async def tell_long_story(
        self, context: RunContext, topic: str = "history of computers"
    ):
        """Called when the user asks for a long story or explanation.
        The agent will speak continuously for a long time to allow testing of backchanneling.

        Args:
            topic: The topic to explain (default: history of computers)
        """
        logger.info(f"Starting long story about: {topic}")

        return (
            f"Please tell a detailed, engaging story about {topic}. "
            "Speak continuously for at least 30-45 seconds. "
            "Make it interesting and informative. "
            "Do not pause for user input unless interrupted."
        )

    @function_tool
    async def ask_question(self, context: RunContext, question: str):
        """Called when the user wants to test how the agent responds to 'yeah' when silent.

        Args:
            question: The question to ask
        """
        logger.info(f"Asking question: {question}")

        return f"Please ask this question and wait for the user's response: {question}"

    @function_tool
    async def count_slowly(self, context: RunContext, count_to: int = 20):
        """Called when the user wants you to count slowly so they can test interruptions.

        Args:
            count_to: The number to count up to (default: 20)
        """
        logger.info(f"Counting to {count_to}")

        return (
            f"Please count from 1 to {count_to} slowly, "
            "pausing briefly between each number. "
            "This gives the user time to test interruptions."
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
    custom_backchanneling_words = [
        "yeah",
        "ok",
        "okay",
        "hmm",
        "uh-huh",
        "right",
        "aha",
        "mhmm",
        "yep",
        "yup",
        "sure",
        "alright",
    ]

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection="stt",
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=False,
        backchanneling_words=custom_backchanneling_words,
        min_interruption_duration=0.5,
        min_interruption_words=0,
    )
    usage_collector = metrics.UsageCollector()
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=InterruptionTestAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)