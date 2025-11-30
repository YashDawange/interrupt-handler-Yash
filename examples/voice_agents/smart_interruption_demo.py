"""Smart Interruption Handling Demo

This example demonstrates the intelligent interruption filtering feature
that allows agents to ignore backchannel words (e.g., "yeah", "ok", "hmm")
when speaking while still responding to genuine interruptions.

Scenarios demonstrated:
1. Agent continues speaking when user says backchannel words
2. Agent responds to backchannel words when silent
3. Agent interrupts for explicit commands
4. Agent handles mixed input correctly
"""

import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
)
from livekit.agents.voice import InterruptionConfig
from livekit.plugins import deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("smart-interruption-demo")
logger.setLevel(logging.INFO)

load_dotenv()


class StorytellerAgent(Agent):
    """Agent that tells stories and demonstrates smart interruption handling."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a friendly storyteller assistant. "
                "When asked, tell engaging stories that are at least 30 seconds long. "
                "Speak naturally and with enthusiasm. "
                "If the user says backchannel words like 'yeah', 'ok', or 'hmm', "
                "continue your story without interruption. "
                "If the user asks you to stop or wait, stop immediately. "
                "Keep responses concise except when telling stories."
            )
        )

    async def on_enter(self):
        """Greet the user when the agent starts."""
        self.session.generate_reply(
            instructions=(
                "Greet the user warmly and explain that you're a storyteller. "
                "Mention that they can say 'yeah', 'ok', or 'hmm' while you're talking "
                "and you'll continue, but if they need you to stop, just say 'wait' or 'stop'. "
                "Then ask what kind of story they'd like to hear."
            )
        )

    @function_tool
    async def tell_long_story(self, context: RunContext, topic: str) -> str:
        """Tell a long, engaging story about the given topic.

        This function demonstrates how the agent continues speaking even when
        the user provides backchannel acknowledgments.

        Args:
            topic: The topic or theme for the story
        """
        logger.info(f"Telling a long story about: {topic}")

        return (
            f"I'll tell you an interesting story about {topic}. "
            f"This story will take about 30-45 seconds to tell, "
            f"so feel free to say 'yeah' or 'ok' to show you're listening - "
            f"I won't stop! But if you need me to stop, just say 'wait' or 'stop'."
        )

    @function_tool
    async def acknowledge_interruption(self, context: RunContext) -> str:
        """Called when user explicitly interrupts.

        Returns:
            str: Acknowledgment message
        """
        logger.info("User interrupted the story")
        return "Got it, I'll stop the story. What would you like to do instead?"


server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm VAD model."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entrypoint for the voice agent with smart interruption handling."""

    # Configure logging
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Create custom interruption configuration
    # You can customize the backchannel words and interrupt keywords here
    interruption_cfg = InterruptionConfig(
        # Words that will be ignored when agent is speaking
        backchannel_words={
            "yeah",
            "ok",
            "okay",
            "hmm",
            "uh-huh",
            "right",
            "aha",
            "sure",
            "got it",
            "yep",
            "mm-hmm",
        },
        # Words that will always cause interruption
        interrupt_keywords={
            "wait",
            "stop",
            "no",
            "hold on",
            "pause",
            "actually",
            "but",
        },
        # Maximum time to wait for STT before treating as interruption
        stt_timeout=0.5,
        # Whether word matching is case-sensitive
        case_sensitive=False,
    )

    # Create the agent session with smart interruption enabled
    session = AgentSession(
        # Speech-to-text
        stt=deepgram.STT(model="nova-3"),
        # Large Language Model
        llm=openai.LLM(model="gpt-4o-mini"),
        # Text-to-speech
        tts=openai.TTS(voice="alloy"),
        # Voice Activity Detection
        vad=ctx.proc.userdata["vad"],
        # Turn detection
        turn_detection=MultilingualModel(),
        # **Enable smart interruption handling**
        enable_smart_interruption=True,
        interruption_config=interruption_cfg,
        # Optional: Enable preemptive generation for lower latency
        preemptive_generation=True,
        # Allow interruptions (smart filter will handle backchannel filtering)
        allow_interruptions=True,
    )

    logger.info(
        "Smart interruption enabled with %d backchannel words and %d interrupt keywords",
        len(interruption_cfg.backchannel_words),
        len(interruption_cfg.interrupt_keywords),
    )

    await session.start(
        agent=StorytellerAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    # Run the agent
    # Test with:
    # 1. Say "Tell me a story about space" -> Agent starts telling story
    # 2. While agent is speaking, say "yeah", "ok", "hmm" -> Agent continues
    # 3. While agent is paused, say "yeah" -> Agent responds
    # 4. While agent is speaking, say "wait" or "stop" -> Agent stops
    # 5. Say "yeah but wait" while speaking -> Agent stops (contains "wait")
    cli.run_app(server)
