"""
Smart Interruption Demo Agent

Demonstrates intelligent handling of soft interruptions vs hard interruptions.
When the agent is speaking, soft acknowledgments like "yeah" or "ok" don't interrupt.
When the agent is silent, the same words are processed as valid responses.
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
    MetricsCollectedEvent,
    RunContext,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class SmartInterruptionAgent(Agent):
    """AI Agent with smart interruption handling capabilities."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are an AI assistant named Alex. "
                "Your goal is to help users test intelligent interruption handling. "
                "When users ask you to explain something or tell a story, speak for at least 30 seconds continuously. "
                "When you ask questions, wait patiently for responses. "
                "Be conversational and natural in your speech patterns. "
                "Avoid using special characters, emojis, or markdown in your responses since this is voice-only."
            ),
        )

    async def on_enter(self):
        """Called when agent enters the conversation."""
        self.session.generate_reply(
            instructions=(
                "Introduce yourself as Alex and explain that you can help test smart interruption handling. "
                "Mention that users can: "
                "(1) Ask you to explain a topic where they can say 'yeah' or 'ok' without interrupting you. "
                "(2) Have you ask questions where 'yeah' or 'ok' will be recognized as answers. "
                "(3) Say 'stop' or 'wait' at any time to interrupt you. "
                "Ask what they'd like to try."
            )
        )

    @function_tool
    async def explain_topic(self, context: RunContext, subject: str):
        """Provide a detailed explanation on a given subject.

        This function is called when users want to test soft interruption handling.
        The agent will provide a continuous explanation that can be tested with
        soft acknowledgments.

        Args:
            subject: The topic to explain in detail
        """
        logger.info(f"Explaining topic: {subject}")
        return (
            f"Provide a comprehensive, detailed explanation about {subject}. "
            "Speak continuously for approximately 30 to 45 seconds. "
            "Make your explanation engaging and informative. "
            "Don't ask questions or pause - just explain continuously."
        )

    @function_tool
    async def pose_question(self, context: RunContext, question_text: str):
        """Ask the user a question and wait for their response.

        This function is used to test that soft words like 'yeah' are correctly
        processed as answers when the agent is silent.

        Args:
            question_text: The question to ask the user
        """
        logger.info(f"Posing question: {question_text}")
        return f"Ask the user this question and then wait silently for their answer: {question_text}"

    @function_tool
    async def enumerate_items(
        self, context: RunContext, start: int = 1, end: int = 15
    ):
        """Count or enumerate items slowly to test interruptions.

        Args:
            start: Starting number (default: 1)
            end: Ending number (default: 15)
        """
        logger.info(f"Enumerating from {start} to {end}")
        return (
            f"Count slowly from {start} to {end}, pausing briefly between each number. "
            "This allows users to test interrupting you with words like 'stop'."
        )


# Create agent server
agent_server = AgentServer()


def initialize_worker(process: JobProcess):
    """Initialize worker resources."""
    process.userdata["vad_model"] = silero.VAD.load()


agent_server.setup_fnc = initialize_worker


@agent_server.rtc_session()
async def session_entrypoint(context: JobContext):
    """Main entry point for agent sessions."""

    # Set logging context
    context.log_context_fields = {"room": context.room.name}

    # Configure soft interruption patterns (using regex for flexibility)
    soft_patterns = os.getenv("SOFT_INTERRUPT_PATTERNS", "").split(",") if os.getenv("SOFT_INTERRUPT_PATTERNS") else None

    # Create agent session with smart interruption handling
    agent_session = AgentSession(
        # Core components
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=context.proc.userdata["vad_model"],
        # Use STT-based turn detection for better transcript integration
        turn_detection="stt",
        # Performance optimizations
        preemptive_generation=True,
        # Interruption handling configuration
        min_interruption_duration=0.5,
        min_interruption_words=0,
        # Smart interruption settings (NEW FEATURE)
        enable_soft_interrupt_filtering=True,
        soft_interrupt_patterns=soft_patterns,  # Can be customized via env var
        # Disable false interruption resumption since we're preventing the interruptions
        resume_false_interruption=False,
    )

    # Set up metrics collection
    usage_metrics = metrics.UsageCollector()

    @agent_session.on("metrics_collected")
    def handle_metrics(event: MetricsCollectedEvent):
        metrics.log_metrics(event.metrics)
        usage_metrics.collect(event.metrics)

    async def report_usage():
        summary = usage_metrics.get_summary()
        logger.info(f"Session usage summary: {summary}")

    context.add_shutdown_callback(report_usage)

    # Start the agent session
    await agent_session.start(
        agent=SmartInterruptionAgent(),
        room=context.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(agent_server)
