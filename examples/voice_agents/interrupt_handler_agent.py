"""
Intelligent Interruption Handler Agent

This agent demonstrates the intelligent interruption handling feature that distinguishes
between passive acknowledgments (backchanneling) and active interruptions.

Key Features:
1. When agent is speaking + user says "yeah/ok/hmm" → Agent continues speaking (IGNORE)
2. When agent is speaking + user says "wait/stop/no" → Agent stops immediately (INTERRUPT)
3. When agent is silent + user says "yeah/ok/hmm" → Agent responds normally (RESPOND)
4. When agent is silent + user says anything → Agent responds normally (RESPOND)
5. Mixed input like "yeah wait" → Agent stops (INTERRUPT) because it contains non-backchannel words

Test Scenarios:
- Scenario 1: Long explanation with user backchanneling ("yeah", "ok", "hmm")
- Scenario 2: Silent agent + user affirmation ("yeah")
- Scenario 3: User correction during agent speech ("no stop")
- Scenario 4: Mixed input ("yeah okay but wait")
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
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("interrupt-handler-agent")
logger.setLevel(logging.DEBUG)

load_dotenv()


class InterruptHandlerAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Alex, an AI assistant designed to test intelligent interruption handling. "
                "You will help demonstrate how the system handles different types of user input. "
                
                "When asked to give a long explanation, provide detailed responses that take 15-20 seconds to speak. "
                "For example, if asked about history, give a comprehensive explanation with multiple facts. "
                
                "Keep your responses natural and conversational. "
                "Do not use emojis, markdown, or special characters. "
                "Speak clearly and at a moderate pace. "
                
                "When the user says short acknowledgments like 'yeah', 'ok', or 'hmm' while you're speaking, "
                "continue your explanation seamlessly. These are signs they're listening. "
                
                "When the user says 'stop', 'wait', or 'no', immediately acknowledge and ask how you can help. "
                
                "Be friendly, patient, and helpful."
            )
        )

    async def on_enter(self):
        """When the agent enters, greet the user and explain what this demo does."""
        logger.info("Agent entering session")
        
        # Generate a greeting
        self.session.generate_reply(allow_interruptions=True)

    @function_tool
    async def get_test_scenario(self, scenario_name: str):
        """
        Get information about test scenarios for interruption handling.
        
        Args:
            scenario_name: The name of the scenario (e.g., "long_explanation", "user_affirmation")
        """
        scenarios = {
            "long_explanation": (
                "Ask the agent to explain something in detail (history, science, etc.). "
                "While it's speaking, say 'yeah', 'ok', or 'hmm'. "
                "The agent should continue without stopping."
            ),
            "user_affirmation": (
                "Wait for the agent to finish speaking and go silent. "
                "Then say 'yeah' or 'ok'. "
                "The agent should respond to your affirmation."
            ),
            "correction": (
                "While the agent is speaking, say 'no', 'stop', or 'wait'. "
                "The agent should stop immediately."
            ),
            "mixed_input": (
                "While the agent is speaking, say something like 'yeah okay but wait'. "
                "The agent should stop because the input contains a command word."
            )
        }
        
        return scenarios.get(
            scenario_name, 
            "Available scenarios: long_explanation, user_affirmation, correction, mixed_input"
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """
    Entry point for the agent session.
    Configures the agent with intelligent interruption handling.
    """
    # Set up logging context
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # Get custom backchannel words from environment variable if provided
    custom_backchannel_words = os.getenv("BACKCHANNEL_WORDS")
    if custom_backchannel_words:
        backchannel_words = [word.strip() for word in custom_backchannel_words.split(",")]
        logger.info(f"Using custom backchannel words: {backchannel_words}")
    else:
        # Use default list (will be set by AgentSession)
        backchannel_words = None
        logger.info("Using default backchannel words")
    
    # Create the agent session with intelligent interruption handling
    session = AgentSession(
        # Speech-to-text (STT) - needed to detect what words the user says
        stt="deepgram/nova-3",
        
        # Large Language Model (LLM) - the agent's brain
        llm="openai/gpt-4.1-mini",
        
        # Text-to-speech (TTS) - the agent's voice
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        
        # Turn detection and VAD
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        
        # Enable preemptive generation for faster responses
        preemptive_generation=True,
        
        # False interruption handling - resumes if user was just making noise
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        
        # ============================================================
        # INTELLIGENT INTERRUPTION HANDLING CONFIGURATION
        # ============================================================
        # This is the key feature: backchannel words to ignore when agent is speaking
        backchannel_words=backchannel_words,
        
        # We want to allow interruptions
        allow_interruptions=True,
        
        # Minimum duration of speech to consider it an interruption (seconds)
        min_interruption_duration=0.3,
        
        # Minimum number of words to interrupt (0 means even 1 word can interrupt)
        # We set this to 0 because we want to handle single-word backchannels
        min_interruption_words=0,
    )
    
    # Set up metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)
    
    # Log agent and user state changes for debugging
    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        logger.debug(f"Agent state: {ev.old_state} -> {ev.new_state}")
    
    @session.on("user_state_changed")
    def _on_user_state_changed(ev):
        logger.debug(f"User state: {ev.old_state} -> {ev.new_state}")
    
    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev):
        logger.debug(f"User transcript ({'final' if ev.is_final else 'interim'}): {ev.transcript}")

    # Start the agent session
    await session.start(
        agent=InterruptHandlerAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)

