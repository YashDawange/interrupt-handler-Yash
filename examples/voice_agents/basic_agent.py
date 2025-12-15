import logging
import re
from typing import Set

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    cli,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Changed logger name for clarity, but logs go to console/file
logger = logging.getLogger("intelligent-agent")

# Loads environment variables from the .env file in the root directory
load_dotenv()


# --- 1. Intelligent Interruption Handler Class (Modular Logic) ---
class IntelligentInterruptionHandler:
    """
    Implements the core logic for intelligent interruption handling.
    """
    # Configurable Ignore List (Key Feature 1)
    IGNORED_WORDS: Set[str] = {
        'yeah', 'ok', 'okay', 'aha', 'uh-huh', 'right', 'mhm', 'hmm', 'um', 'uh'
    }

    def __init__(self, is_agent_speaking: bool = False):
        self.is_agent_speaking = is_agent_speaking

    def set_agent_speaking_state(self, is_speaking: bool):
        """Updates the agent's speaking state (Key Feature 2: State-Based Filtering)."""
        self.is_agent_speaking = is_speaking

    def is_ignored(self, transcription_text: str) -> bool:
        """
        Applies the core logic matrix.
        - True: Passive acknowledgement while speaking -> IGNORE.
        - False: Active interruption OR agent is silent -> RESPOND/INTERRUPT.
        """
        if not transcription_text:
            return False
            
        text = transcription_text.lower().strip().replace('.', '').replace('?', '')
        words = re.findall(r'\b\w+\b', text)

        # Agent is SILENT: Always treat as valid input (RESPOND/INTERRUPT)
        if not self.is_agent_speaking:
            return False

        # Agent is SPEAKING: Check for filler words (Strict Requirement)
        
        # Semantic Interruption (Key Feature 3): Check if *all* words are fillers.
        is_only_filler = all(word in self.IGNORED_WORDS for word in words)

        if is_only_filler:
            # Only filler words -> IGNORE
            return True
        else:
            # Contains command/non-filler -> INTERRUPT
            return False


# --- 2. LiveKit Agent Implementation with Logic Integration ---
# This class replaces the original MyAgent class.
class IntelligentAgent(Agent):
    """
    A custom agent that manages its speaking state and filters user input.
    """
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You are a conversational AI assistant. "
            "You are curious and friendly, and have a sense of humor. "
            "Keep your responses concise and to the point. Speak English.",
        )
        # Initialize the custom logic handler
        self.interruption_handler = IntelligentInterruptionHandler(is_agent_speaking=False)

    # State Management Hooks (Critical for updating the handler's internal state)
    async def on_agent_speech_start(self, handle):
        """Called by AgentSession when the agent begins speaking."""
        self.interruption_handler.set_agent_speaking_state(True)

    async def on_agent_speech_end(self, handle):
        """Called by AgentSession when the agent finishes speaking."""
        self.interruption_handler.set_agent_speaking_state(False)
    
    
    # FIXED: Handling ChatContext and extracting transcript string)
    async def on_user_turn_completed(self, chat_context, *args, **kwargs):
        """
        Intercepts the final user transcript to apply the context-aware filtering.
        The LiveKit SDK is passing the ChatContext as the first argument.
        The actual transcript text is expected to be in kwargs['new_message'].text
        or as a message object attribute.
        """
        
        
        # 1. Safely extract the transcript string from the keyword arguments
        # The transcription text is typically found inside the 'new_message' keyword argument
        # passed by the framework.
        new_message = kwargs.get('new_message')
        if new_message and hasattr(new_message, 'text'):
            transcript = new_message.text
        else:
            # Fallback (should not happen with voice agents, but safe to include)
            transcript = ""

        if not transcript:
            # If there's no actual transcribed text, just skip it.
            return

        # 2. Apply the filtering logic to the actual string
        is_ignored_input = self.interruption_handler.is_ignored(transcript)

        if is_ignored_input:
            # Scenario 1 (IGNORE): Prevent the LLM from processing.
            logger.warning(f"[PASSIVE ACKNOWLEDGE] Ignoring input: '{transcript}'. Agent continues.")
            return

        # Scenarios 2, 3, & 4 (INTERRUPT/RESPOND): Proceed with processing.
        logger.info(f"[ACTIVE TURN] Processing input: '{transcript}'.")
        
        # Call the base class method. We must pass the ChatContext as the first argument, 
        # followed by the rest of the original arguments.
        await super().on_user_turn_completed(chat_context, *args, **kwargs)
        
    async def on_enter(self):
        # Initial greeting is the first agent speech
        await self.session.generate_reply(instructions="greet the user and ask about their day")

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        ... (omitted docstring for brevity)
        """
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."


server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # Prewarm VAD as is standard practice
    vad = silero.VAD.load()

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=vad,
        
        # These parameters enable the underlying "false interruption" recovery 
        # which is essential for our filtering logic to work seamlessly.
        preemptive_generation=True,
        resume_false_interruption=True, 
        false_interruption_timeout=1.0, 
    )

    await session.start(
        agent=IntelligentAgent(), # Use our custom agent
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(server)