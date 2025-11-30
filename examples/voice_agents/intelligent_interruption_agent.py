"""
Intelligent Interruption Handling Agent

This example demonstrates state-aware interruption handling using the backchannel_words
feature. The agent distinguishes between passive acknowledgments (backchannels) and
active interruptions based on its current speaking state.

Key Features:
- Ignores filler words ("yeah", "ok", "hmm") when agent is speaking
- Processes the same words as valid input when agent is silent
- Handles mixed input (e.g., "yeah but wait") as interruptions
- Configurable list of backchannel words

Test Scenarios:
1. Long Explanation: Agent reads a long paragraph; user says "okay... yeah... uh-huh"
   Result: Agent continues without interruption

2. Passive Affirmation: Agent asks "Are you ready?" and goes silent; user says "Yeah"
   Result: Agent processes "Yeah" and proceeds

3. Active Interruption: Agent is counting; user says "No stop"
   Result: Agent stops immediately

4. Mixed Input: Agent is speaking; user says "Yeah okay but wait"
   Result: Agent stops (contains non-backchannel word "wait")
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
)
from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, openai, silero

logger = logging.getLogger("intelligent-interruption-agent")
logger.setLevel(logging.INFO)

load_dotenv()

# Configure backchannel words - these will be ignored when agent is speaking
# You can customize this list via environment variable
DEFAULT_BACKCHANNEL_WORDS = [
    "yeah",
    "ok",
    "okay",
    "hmm",
    "uh-huh",
    "mm-hmm",
    "right",
    "sure",
    "got it",
    "aha",
    "mhm",
    "yep",
    "yup",
]


def get_backchannel_words() -> list[str]:
    """Load backchannel words from environment or use defaults."""
    env_words = os.getenv("BACKCHANNEL_WORDS")
    if env_words:
        return [word.strip().lower() for word in env_words.split(",")]
    return DEFAULT_BACKCHANNEL_WORDS


class IntelligentAgent(Agent):
    """Agent that demonstrates intelligent interruption handling."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Kelly, a helpful AI assistant demonstrating intelligent interruption handling. "
                "Keep your responses conversational and natural. "
                "When explaining things, speak in complete sentences and paragraphs. "
                "Do not use emojis, asterisks, or special characters in your responses."
            ),
        )

    async def on_enter(self):
        """Called when agent enters the session."""
        logger.info("IntelligentAgent entered session")
        # Generate an initial greeting
        self.session.generate_reply(
            instructions=(
                "Greet the user warmly and explain that you're demonstrating intelligent "
                "interruption handling. Tell them they can say 'yeah' or 'ok' while you're "
                "speaking without interrupting you, but they can say 'wait' or 'stop' to "
                "interrupt. Ask if they'd like to try it out."
            )
        )

    @function_tool
    async def tell_long_story(self, context: RunContext):
        """Tell a long story to demonstrate backchannel handling.

        This function is useful for testing whether the agent continues speaking
        when the user provides passive acknowledgments like 'yeah' or 'hmm'.
        """
        logger.info("User requested a long story")

        story = (
            "Let me tell you an interesting story about artificial intelligence. "
            "In the early days of AI research, scientists dreamed of creating machines "
            "that could think like humans. Alan Turing proposed his famous test in 1950, "
            "suggesting that if a machine could fool a human into thinking it was human, "
            "it could be considered intelligent. Fast forward to today, and we have "
            "language models that can engage in sophisticated conversations, understand "
            "context, and even demonstrate creativity. The journey from those early "
            "symbolic AI systems to modern neural networks has been fascinating, "
            "involving breakthroughs in machine learning, natural language processing, "
            "and computational power. What's particularly exciting is how AI is now "
            "being used to help solve real-world problems, from medical diagnosis to "
            "climate modeling to creative endeavors like writing and art."
        )

        return story

    @function_tool
    async def count_to_ten(self, context: RunContext):
        """Count from one to ten slowly.

        This function is useful for testing interruptions with a predictable speech pattern.
        """
        logger.info("User requested counting to ten")
        return "I'll count to ten for you: one, two, three, four, five, six, seven, eight, nine, ten. There you go!"

    @function_tool
    async def explain_weather(self, context: RunContext, location: str = "your area"):
        """Explain how weather systems work.

        Args:
            location: The location to explain weather for
        """
        logger.info(f"User asked about weather in {location}")

        explanation = (
            f"Weather systems in {location} are fascinating. They're influenced by "
            "several factors including atmospheric pressure, temperature gradients, "
            "humidity levels, and wind patterns. High pressure systems typically bring "
            "clear skies and calm conditions, while low pressure systems often result "
            "in clouds and precipitation. The interaction between warm and cold air masses "
            "creates fronts that can produce various weather phenomena. Understanding "
            "these patterns helps meteorologists predict what conditions we'll experience."
        )

        return explanation


server = AgentServer()


def prewarm(proc: JobProcess):
    """Pre-load models to reduce startup latency."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Entry point for the intelligent interruption agent."""

    # Load backchannel words configuration
    backchannel_words = get_backchannel_words()

    logger.info(
        f"Starting session with backchannel filtering enabled. "
        f"Configured words: {', '.join(backchannel_words)}"
    )

    # Configure the session with intelligent interruption handling
    session = AgentSession(
        # Core models
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="echo"),
        vad=ctx.proc.userdata["vad"],
        # Interruption settings
        allow_interruptions=True,
        min_interruption_duration=0.5,  # Minimum 0.5s of speech to consider interruption
        min_interruption_words=0,  # Don't require minimum words (handled by backchannel filter)
        # Intelligent interruption handling - the key feature!
        backchannel_words=backchannel_words,
        # False interruption handling for better UX
        resume_false_interruption=True,
        false_interruption_timeout=1.5,
        # Performance optimizations
        preemptive_generation=True,
    )

    # Log metrics
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        logger.info(f"Agent state changed: {ev.old_state} -> {ev.new_state}")

    @session.on("user_state_changed")
    def _on_user_state_changed(ev):
        logger.info(f"User state changed: {ev.old_state} -> {ev.new_state}")

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev):
        if ev.is_final:
            logger.info(f"User said: '{ev.transcript}' (final)")
        else:
            logger.debug(f"User interim: '{ev.transcript}'")

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Session ended. Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the agent
    await session.start(
        agent=IntelligentAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    # Configure logging for better visibility
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cli.run_app(server)

