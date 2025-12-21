"""
Basic Voice Agent with Intelligent Interruption Handling

This agent demonstrates the Temporal-Semantic Fusion (TSF) approach for handling
user interruptions. It ignores backchanneling ("yeah", "ok") while speaking but
responds to active commands ("stop", "wait").

Usage:
    python basic_agent.py dev     # Development mode with hot reload
    python basic_agent.py console # Terminal testing mode
    python basic_agent.py start   # Production mode
"""

import logging
import asyncio
import string
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
    UserInputTranscribedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

# ============================================================================
# INTELLIGENT INTERRUPTION HANDLING (TSF - Temporal-Semantic Fusion)
# ============================================================================

# Configurable list of backchannel words to ignore when agent is speaking
# Can be overridden via IGNORE_WORDS environment variable (comma-separated)
DEFAULT_IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "aha", "right", "uh-huh",
    "yep", "yup", "sure", "got it", "i see", "mhm", "uh huh",
    "mm", "mmm", "mhmm", "yes", "yea", "ya"
}

def get_ignore_words():
    """Get ignore words from environment or use defaults."""
    env_words = os.getenv("IGNORE_WORDS")
    if env_words:
        return {word.strip().lower() for word in env_words.split(",")}
    return DEFAULT_IGNORE_WORDS

def is_backchannel(text: str, ignore_words: set) -> bool:
    """Check if text consists entirely of backchannel words."""
    # Sanitize: lowercase, strip, remove punctuation
    text = text.lower().strip()
    text = text.translate(str.maketrans('', '', string.punctuation))
    if not text:
        return True
    words = text.split()
    return all(word in ignore_words for word in words)

def setup_interruption_handler(session: AgentSession):
    """
    Set up intelligent interruption handling for an AgentSession.
    
    This implements TSF (Temporal-Semantic Fusion):
    - Temporal Gate: Check if agent is speaking
    - Semantic Analysis: Classify input as backchannel or command
    - Decision: Ignore backchannels, interrupt on commands
    """
    ignore_words = get_ignore_words()
    
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: UserInputTranscribedEvent):
        # TEMPORAL GATE: If agent is NOT speaking, all input is valid
        if session.agent_state != "speaking":
            logger.info(f"Agent silent - processing input: '{event.transcript}'")
            return
        
        transcript = event.transcript
        
        # SEMANTIC ANALYSIS: Is this a backchannel or a command?
        if is_backchannel(transcript, ignore_words):
            # BACKCHANNEL: Ignore - agent continues speaking
            logger.info(f"Backchannel ignored: '{transcript}'")
        else:
            # COMMAND: Trigger interruption
            logger.info(f"Interrupt triggered: '{transcript}'")
            asyncio.create_task(session.interrupt(force=True))

load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice. "
            "With that in mind keep your responses concise and to the point. "
            "Do not use emojis, asterisks, markdown, or other special characters in your responses. "
            "You are curious and friendly, and have a sense of humor. "
            "You will speak english to the user. "
            "If the user says 'stop' or 'wait', acknowledge that you were interrupted. "
            "If the user says 'yeah' or 'ok' while you are silent, treat it as confirmation and continue the conversation.",
        )

    async def on_enter(self):
        # Start with a longer message to demonstrate interruption handling
        await self.session.say(
            "Hello! I'm Kelly, your voice assistant with intelligent interruption handling. "
            "While I'm speaking, you can say 'yeah', 'ok', or 'hmm' to show you're listening, "
            "and I will continue without stopping. "
            "However, if you say 'stop' or 'wait', I will pause immediately. "
            "Now, let me tell you a bit about myself. "
            "I'm designed to be helpful, concise, and friendly. "
            "I can help you with various tasks like looking up the weather or just having a conversation. "
            "Feel free to ask me anything!",
            allow_interruptions=False  # Disable auto-interruption; we handle it manually via TSF
        )

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        Ensure the user's location (city or region) is provided.
        When given a location, please estimate the latitude and longitude of the location and
        do not ask the user for them.

        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt="deepgram/nova-3",
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm="openai/gpt-4.1-mini",
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
        # when it's detected, you may resume the agent's speech
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

    # ========================================================================
    # SET UP INTELLIGENT INTERRUPTION HANDLER (TSF)
    # ========================================================================
    # This registers the user_input_transcribed event handler that:
    # - Ignores "yeah", "ok", "hmm" while agent is speaking (backchannels)
    # - Triggers interruption for "stop", "wait" (commands)
    # - Processes all input normally when agent is silent
    setup_interruption_handler(session)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # uncomment to enable the Krisp BVC noise cancellation
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
