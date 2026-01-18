import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
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

logger = logging.getLogger("intelligent-interrupt-agent")
logger.setLevel(logging.DEBUG)

load_dotenv()


class IntelligentInterruptAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful history teacher named Professor Smith.
            You love giving detailed explanations about historical events.
            When asked about any topic, give a fairly long and detailed response
            (at least 3-4 sentences) to demonstrate the interruption handling.

            Keep in mind:
            - Don't use emojis or special characters in your responses
            - Speak naturally and conversationally
            - If the user says words like "yeah", "ok", "uh-huh" while you're speaking,
              these are just signs they're listening - keep talking!
            - If the user says "stop", "wait", or asks a question, stop and listen

            Start by introducing yourself and asking what topic they'd like to learn about.""",
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def tell_long_story(
        self,
        context: RunContext,
        topic: str,
    ):
        logger.info(f"Telling a long story about: {topic}")
        return f"""Here's an extensive story about {topic}:

        The history of {topic} is fascinating and spans many centuries.
        It began in ancient times when people first started exploring this subject.
        Over the years, many great thinkers contributed their ideas and discoveries.
        The developments in this field have shaped our modern understanding significantly.
        Today, we continue to build upon this rich foundation of knowledge.
        """


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Create the agent session with intelligent interruption handling
    session = AgentSession(
        # Speech-to-text
        stt="deepgram/nova-3",
        # LLM
        llm="openai/gpt-4.1-mini",
        # Text-to-speech
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # Turn detection
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # Allow interruptions
        allow_interruptions=True,
        # Standard interruption settings
        min_interruption_duration=0.5,
        min_interruption_words=0,
        # ===== INTELLIGENT INTERRUPTION HANDLING =====
        # Enable ignoring backchanneling words while the agent is speaking
        ignore_backchanneling=True,
        # Optional: Customize the list of words to ignore (uses sensible defaults if not provided)
        # backchanneling_words=["yeah", "ok", "uh-huh", "hmm", "right", "gotcha"],
        # Optional: Customize the list of words that always interrupt
        # interrupt_words=["stop", "wait", "hold on", "no", "pause"],
        # This feature prevents the following words from interrupting the agent while speaking:
        # - "yeah", "yep", "yes", "yup", "ok", "okay"
        # - "hmm", "uh-huh", "mhm", "mm-hmm"
        # - "right", "aha", "ah", "oh", "i see"
        # - "sure", "gotcha", "alright", "cool", "nice", "great", "good"
        #
        # But these words will ALWAYS cause an interruption:
        # - "stop", "wait", "hold on", "pause", "no", "cancel"
        # - "question", "but", "however", "actually", "excuse me"
        # - "let me", "can i", "may i", "i have", "i need", "i want"
    )

    # Set up metrics logging
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session
    await session.start(
        agent=IntelligentInterruptAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(
        entrypoint=entrypoint,
        prewarm_fnc=prewarm,
    )
