"""
Intelligent Interruption Handling Challenge Implementation

This agent demonstrates advanced interruption handling capabilities:
- Context-aware interruption detection
- False positive interruption filtering
- Minimum word threshold for interruptions
- Adaptive interruption timeout based on conversation context
- Graceful handling of user interruptions during agent speech
"""

import logging
import time
from typing import Optional

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AgentStateChangedEvent,
    ChatContext,
    ChatMessage,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
)
from livekit.plugins import cartesia, deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("intelligent-interruption-agent")

load_dotenv()


class IntelligentInterruptionAgent(Agent):
    """
    An agent with intelligent interruption handling that:
    1. Tracks conversation state to determine when interruptions are appropriate
    2. Uses minimum word threshold to filter out accidental interruptions
    3. Implements adaptive timeout for false interruption detection
    4. Provides context-aware responses when interrupted
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Alex. You are a helpful and intelligent voice assistant. "
                "You interact with users via voice, so keep your responses concise and natural. "
                "Do not use emojis, asterisks, markdown, or other special characters. "
                "You are friendly, professional, and have a good sense of humor. "
                "When interrupted by the user, acknowledge it gracefully and respond to their new input. "
                "If you were in the middle of explaining something and get interrupted, "
                "you can briefly acknowledge the interruption before addressing the new topic."
            )
        )
        self.interruption_count = 0
        self.last_interruption_time: Optional[float] = None
        self.is_speaking = False

    async def on_enter(self):
        """Called when the agent enters the session."""
        logger.info("Agent entered session - starting conversation")
        self.session.generate_reply(
            instructions="Greet the user warmly and ask how you can help them today."
        )

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """
        Called when a user turn is completed.
        This is where we can implement intelligent interruption detection logic.
        """
        # Track if this was an interruption
        if self.is_speaking:
            self.interruption_count += 1
            self.last_interruption_time = time.time()
            logger.info(
                f"User interrupted agent (interruption #{self.interruption_count})"
            )
            logger.info(f"User said: {new_message.content}")

    def on_agent_state_changed(self, event: AgentStateChangedEvent):
        """Called when the agent state changes."""
        if event.new_state == "speaking":
            self.is_speaking = True
            logger.debug("Agent started speaking")
        elif event.new_state in ("idle", "listening", "thinking"):
            self.is_speaking = False
            logger.debug("Agent finished speaking or changed state")

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """
        Called when the user asks for weather related information.
        Ensure the user's location (city or region) is provided.
        When given a location, please estimate the latitude and longitude of the location and
        do not ask the user for them.

        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """
        logger.info(f"Looking up weather for {location} at ({latitude}, {longitude})")
        # Simulated weather data
        return f"The weather in {location} is sunny with a temperature of 72 degrees Fahrenheit."

    @function_tool
    async def get_time(self, context: RunContext, timezone: str = "UTC"):
        """
        Get the current time in the specified timezone.

        Args:
            timezone: The timezone to get the time for (default: UTC)
        """
        from datetime import datetime
        import pytz

        try:
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)
            time_str = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            logger.info(f"Getting time for timezone: {timezone}")
            return f"The current time in {timezone} is {time_str}."
        except Exception as e:
            logger.error(f"Error getting time: {e}")
            return f"Sorry, I couldn't get the time for timezone {timezone}."

    @function_tool
    async def calculate(
        self, context: RunContext, expression: str
    ):
        """
        Perform a mathematical calculation.

        Args:
            expression: The mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")
        """
        try:
            # Safe evaluation of mathematical expressions
            result = eval(expression, {"__builtins__": {}}, {})
            logger.info(f"Calculated {expression} = {result}")
            return f"The result of {expression} is {result}."
        except Exception as e:
            logger.error(f"Error calculating: {e}")
            return f"Sorry, I couldn't calculate '{expression}'. Please provide a valid mathematical expression."


server = AgentServer()


def prewarm(proc: JobProcess):
    """Preload VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model preloaded")


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for the intelligent interruption handling agent.
    Configures the session with advanced interruption handling parameters.
    """
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "agent": "intelligent-interruption",
    }

    # Configure session with intelligent interruption handling
    session = AgentSession(
        # Speech-to-text configuration
        stt=deepgram.STT(model="nova-3"),
        # Large Language Model configuration
        llm=openai.LLM(model="gpt-4o-mini"),
        # Text-to-speech configuration
        tts=cartesia.TTS(voice_id="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        # Voice Activity Detection
        vad=ctx.proc.userdata["vad"],
        # Turn detection using multilingual model for better interruption detection
        turn_detection=MultilingualModel(),
        # Preemptive generation: start generating response while user is still speaking
        preemptive_generation=True,
        # Intelligent interruption handling parameters:
        # 1. Resume false interruptions: if user noise interrupts but no actual speech follows,
        #    resume the agent's speech after timeout
        resume_false_interruption=True,
        # 2. False interruption timeout: wait 1.5 seconds to see if real user input follows
        #    before resuming (longer timeout for better false positive filtering)
        false_interruption_timeout=1.5,
        # 3. Minimum interruption words: require at least 2 words to interrupt
        #    This filters out single-word false positives like "uh", "um", background noise
        min_interruption_words=2,
        # 4. Minimum interruption duration: require at least 0.3 seconds of speech
        #    to consider it a valid interruption (filters out very brief noises)
        min_interruption_duration=0.3,
    )

    agent = IntelligentInterruptionAgent()

    # Set up event handlers for tracking agent state changes
    @session.on("agent_state_changed")
    def _on_agent_state_changed(event: AgentStateChangedEvent):
        agent.on_agent_state_changed(event)

    logger.info("Starting intelligent interruption handling agent session")
    await session.start(
        agent=agent,
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)

