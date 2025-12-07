"""
Intelligent Interruption Handling Agent (Google Gemini Version)

This example demonstrates the intelligent backchanneling filter that allows the agent
to distinguish between:
- Passive acknowledgements ("yeah", "ok", "hmm") - IGNORED while agent is speaking
- Active interruptions ("stop", "wait", "no") - ALWAYS interrupt the agent
- Mixed inputs ("yeah wait") - Contain commands, so interrupt

This version uses Google services:
- STT: Google Cloud Speech-to-Text
- LLM: Google Gemini
- TTS: Google Cloud Text-to-Speech

Required environment variables:
- GOOGLE_API_KEY: Your Google API key for Gemini
- GOOGLE_APPLICATION_CREDENTIALS: Path to your Google Cloud service account JSON (for STT/TTS)
  OR use Application Default Credentials

Key features:
1. Agent continues speaking over filler words like "yeah", "ok", "hmm"
2. Agent stops immediately when user says "stop", "wait", or "no"
3. When agent is silent, "yeah" is treated as valid input (e.g., answering "Are you ready?")
4. Mixed inputs like "yeah but wait" trigger interruption due to command word "wait"

Test scenarios:
1. The Long Explanation: Agent reads long text, user says "yeah... ok... uh-huh" -> No break
2. The Passive Affirmation: Agent asks "Are you ready?", user says "Yeah" -> Agent proceeds
3. The Correction: Agent is counting, user says "No stop" -> Agent cuts off immediately
4. The Mixed Input: Agent speaking, user says "Yeah okay but wait" -> Agent stops
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
from livekit.agents.voice import (
    BackchannelingConfig,
    BackchannelingFilter,
    set_global_filter,
    DEFAULT_FILLER_WORDS,
    DEFAULT_COMMAND_WORDS,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.plugins import google

logger = logging.getLogger("intelligent-interrupt-agent")

load_dotenv()


def setup_backchanneling_filter():
    """Configure the backchanneling filter for intelligent interruption handling.
    
    You can customize the filler words (ignored while speaking) and command words
    (always trigger interruption) based on your use case.
    """
    # Option 1: Use default configuration
    # The filter is automatically enabled with sensible defaults
    
    # Option 2: Customize via environment variables
    # Set LIVEKIT_BACKCHANNELING_FILLER_WORDS=yeah,ok,hmm,right
    # Set LIVEKIT_BACKCHANNELING_COMMAND_WORDS=stop,wait,no,help
    
    # Option 3: Programmatic configuration (shown below)
    custom_filler_words = frozenset([
        # Standard backchanneling
        "yeah", "yea", "ya", "yep", "yup", "yes",
        "ok", "okay", "k",
        "hmm", "hm", "mm", "mmhmm", "mhm", "uh-huh", "uh huh",
        "right", "alright",
        "sure",
        "got it", "gotcha",
        "aha", "ah", "oh",
        "i see",
        "cool", "nice", "good", "great",
        "go on", "go ahead", "continue",
        # Add any domain-specific acknowledgements
        "interesting",
        "understood",
    ])
    
    custom_command_words = frozenset([
        # Stop/interrupt commands
        "stop", "wait", "hold", "pause", "halt",
        "no", "nope", "nah",
        # Questions (user wants to ask something)
        "what", "why", "how", "when", "where", "who",
        # Clarification
        "repeat", "again", "sorry", "pardon",
        # Disagreement/correction
        "actually", "but", "however", "wrong",
        # Change requests
        "skip", "next", "different", "another",
        # Help
        "help", "explain",
    ])
    
    config = BackchannelingConfig(
        enabled=True,
        filler_words=custom_filler_words,
        command_words=custom_command_words,
        case_sensitive=False,  # "YEAH" and "yeah" are treated the same
    )
    
    filter_instance = BackchannelingFilter(config)
    set_global_filter(filter_instance)
    
    logger.info(
        "Backchanneling filter configured",
        extra={
            "filler_words": len(custom_filler_words),
            "command_words": len(custom_command_words),
        }
    )


class IntelligentInterruptAgent(Agent):
    """An agent with intelligent interruption handling.
    
    This agent demonstrates proper handling of backchanneling vs. real interruptions.
    It will continue speaking when users say filler words, but stop when they
    give commands or ask questions.
    """
    
    def __init__(self) -> None:
        super().__init__(
            instructions="""Your name is Alex. You are a helpful AI assistant.

You should demonstrate intelligent interruption handling. When explaining something:
- Continue speaking if the user says acknowledgement words like "yeah", "ok", "hmm"
- Stop immediately if the user says command words like "stop", "wait", "no"

Your responses should be conversational but informative. When asked to explain
something, give a detailed response so users can test the interruption handling.

Do not use emojis, asterisks, or markdown in your responses.
Keep your tone friendly and professional.""",
        )

    async def on_enter(self):
        """Generate initial greeting when agent enters the session."""
        self.session.generate_reply()

    @function_tool
    async def tell_long_story(self, context: RunContext) -> str:
        """Tell a long story to test interruption handling.
        
        The user can say "yeah", "ok", or "hmm" while you're talking
        and you should continue. If they say "stop" or "wait", stop immediately.
        """
        logger.info("Starting long story for interruption test")
        return """Here's a fascinating story about the history of artificial intelligence.
        
It all began in the 1950s when Alan Turing proposed the famous Turing test. 
He asked the question: Can machines think? This sparked decades of research
and development in computer science.

In 1956, John McCarthy coined the term artificial intelligence at the Dartmouth
Conference. This marked the official birth of AI as a field of study.

The early years saw the development of rule-based systems and expert systems.
Programs like ELIZA simulated conversation, while MYCIN diagnosed diseases.

The 1980s brought neural networks back into focus. Researchers discovered
that these brain-inspired systems could learn patterns from data.

In 2012, deep learning revolutionized AI with AlexNet winning ImageNet.
Since then, we've seen transformers, GPT models, and large language models.

Today, AI assists in everything from writing to coding to creative tasks.
The future holds even more exciting possibilities as technology evolves.

Would you like me to continue with more details about any era?"""

    @function_tool
    async def count_numbers(
        self, context: RunContext, start: int = 1, end: int = 20
    ) -> str:
        """Count numbers out loud from start to end.
        
        This is useful for testing interruption - say "stop" to interrupt.
        
        Args:
            start: The number to start counting from
            end: The number to stop counting at
        """
        logger.info(f"Starting count from {start} to {end}")
        numbers = list(range(start, end + 1))
        return f"I'll count from {start} to {end}: " + ", ".join(
            str(n) for n in numbers
        ) + ". That's the count!"

    @function_tool
    async def ask_ready_question(self, context: RunContext) -> str:
        """Ask the user if they are ready.
        
        This tests that "yeah" is properly handled as a valid response
        when the agent is NOT speaking.
        """
        logger.info("Asking ready question")
        return "Are you ready to begin?"


server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm the agent process with required models."""
    proc.userdata["vad"] = silero.VAD.load()
    
    # Configure the backchanneling filter during prewarm
    setup_backchanneling_filter()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entry point for the voice agent session."""
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    session = AgentSession(
        # STT: Google Cloud Speech-to-Text
        # Using default model for streaming recognition
        stt=google.STT(
            languages=["en-US"],
            model="latest_long",  # Works in global location
        ),
        # LLM: Google Gemini
        # gemini-2.0-flash is fast and good for voice applications
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
        # TTS: Google Cloud Text-to-Speech
        # Using Chirp3 HD voice for natural speech
        tts=google.TTS(
            voice_name="en-US-Chirp3-HD-Charon",  # or "en-US-Neural2-D" for Neural2
            language="en-US",
            speaking_rate=1.0,
        ),
        # Turn detection and VAD
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # Enable preemptive generation for faster responses
        preemptive_generation=True,
        # Enable false interruption handling to resume if user stops mid-word
        resume_false_interruption=True,
        false_interruption_timeout=1.5,
        # These settings work well with the backchanneling filter:
        # - Allow interruptions so commands like "stop" work
        # - Set reasonable duration so very short sounds don't trigger
        allow_interruptions=True,
        min_interruption_duration=0.5,
        min_interruption_words=0,  # Let the backchanneling filter handle word-level filtering
    )

    # Log metrics for debugging
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session with the intelligent interrupt agent
    await session.start(
        agent=IntelligentInterruptAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)

