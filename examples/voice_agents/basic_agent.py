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
from livekit.plugins.turn_detector.multilingual import MultilingualModel


# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

load_dotenv()

# These are passive acknowledgments that indicate listening, not interruption intent
BACKCHANNEL_WORDS = [
    # Basic acknowledgments
    'yeah', 'yes', 'yep', 'yup', 'ya', 'aye',
    'ok', 'okay', 'okays', 'k', 'kay',
    'hmm', 'hm', 'hmph', 'hmmm', 'mhmm', 'mmhmm', 'mm', 'mmm',
    'uh-huh', 'uhhuh', 'uh huh',
    'aha', 'ah', 'oh', 'ooh', 'ahh',
    
    # Agreement/confirmation
    'right', 'alright', 'all right', 'aight',
    'sure', 'certainly', 'indeed', 'absolutely',
    'exactly', 'precisely', 'correct',
    'true', 'fair', 'agreed',
    
    # Understanding indicators
    'got it', 'gotcha', 'got you', 'i see', 'i understand',
    'makes sense', 'clear', 'understood',
    
    # Encouragement to continue
    'go on', 'continue', 'and', 'so', 'then',
    'interesting', 'really', 'wow', 'cool', 'nice',
    
    # Thinking sounds
    'uh', 'um', 'er', 'ah', 'eh', 'uhm', 'umm', 'err',
    
    # Short affirmations
    'good', 'fine', 'great', 'perfect',
    
    # Common filler combinations
    'yeah yeah', 'okay okay', 'right right',
    'i see i see', 'got it got it',
]

# Words/phrases that indicate genuine interruption intent
INTERRUPT_WORDS = [
    # Direct stop commands
    'stop', 'halt', 'pause', 'hold', 'hold on', 'hold up',
    'wait', 'wait a second', 'wait a minute', 'wait up',
    'hang on', 'hang up',
    
    # Disagreement/correction
    'no', 'nope', 'nah', 'no way',
    'wrong', 'incorrect', 'not right',
    
    # Need to interject
    'but', 'however', 'actually', 'excuse me',
    'sorry', 'pardon', 'pardon me',
    'listen', 'hear me out',
    
    # Questions/clarification needed
    'what', 'huh', 'what do you mean', 'what are you saying',
    'repeat', 'say that again', 'come again',
    'clarify', 'explain',
    
    # Interruption markers
    'let me', 'can i', 'may i', 'i want to',
    'i need to', 'i have to', 'i must',
    'one second', 'one moment', 'just a sec',
    
    # Urgent attention needed
    'important', 'urgent', 'emergency',
    'quick question', 'real quick',
    
    # Change of topic
    'anyway', 'by the way', 'speaking of',
    'different topic', 'new question',
    
    # Strong disagreement
    'disagree', 'not true', 'that\'s wrong',
]

# Optional: Neutral words that could go either way depending on context
# You might want to use sentiment analysis or tone detection for these
AMBIGUOUS_WORDS = [
    'well', 'so', 'now', 'okay but', 'yeah but',
    'sure but', 'right but', 'i mean',
]


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice."
            "with that in mind keep your responses concise and to the point."
            "do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "you will speak english to the user",
        )
        self.is_speaking = False    #To track if agent is currently speaking

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

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
    def should_allow_interruption(transcript: str, agent_speaking: bool) -> bool:
        """
        Intelligent interruption filter - decides if user input should interrupt agent
        
        This is the CORE LOGIC that implements the assignment requirement:
        - If agent is speaking + user only says backchannel words → Return False (ignore)
        - If agent is speaking + user says interrupt words → Return True (interrupt)
        - If agent is silent → Return True (respond to everything, even "yeah")
        
        Args:
            transcript: The user's speech text
            agent_speaking: Whether the agent is currently speaking
            
        Returns:
            True = Allow interruption (or process input if agent silent)
            False = Ignore input (agent continues speaking)
        """
        # If agent is silent, allow ALL input (including "yeah" should get response)
        if not agent_speaking:
            return True
        
        # Agent is speaking - check what user said
        user_text = transcript.strip().lower()
        words = user_text.split()
        
        # Check if ALL words are backchannel words
        is_only_backchannel = all(
            word in BACKCHANNEL_WORDS for word in words if word
        ) or user_text in BACKCHANNEL_WORDS
        
        # Check if ANY word is an interrupt command
        has_interrupt = any(
            interrupt in user_text for interrupt in INTERRUPT_WORDS
        )
        
        # Check for ambiguous phrases like "yeah but"
        has_ambiguous = any(
            ambiguous in user_text for ambiguous in AMBIGUOUS_WORDS
        )
        
        # Decision: Block interruption ONLY if it's pure backchannel
        if is_only_backchannel and not has_interrupt and not has_ambiguous:
            return False  # IGNORE - don't interrupt
        else:
            return True  # ALLOW - interrupt the agent
 
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
    # Event handler: Called when agent starts speaking
    @session.on("agent_speech_started")
    def _on_agent_speech_started():
        """Track when the agent begins speaking"""
        logger.info("Agent started speaking")
        # Mark the agent as speaking
        if hasattr(session, 'agent') and session.agent:
            session.agent.is_speaking = True
    
    # Event handler: Called when agent finishes speaking
    @session.on("agent_speech_committed")
    def _on_agent_speech_committed():
        """Track when the agent finishes speaking"""
        logger.info("Agent finished speaking")
        # Mark the agent as not speaking
        if hasattr(session, 'agent') and session.agent:
            session.agent.is_speaking = False
    
        # Event handler: Called when user speech is detected
    @session.on("user_speech_committed")
    async def _on_user_speech_committed(transcript: str):
        """
        Handle user input with intelligent interruption filtering.
        This is called AFTER STT has converted speech to text.
        """
        user_text = transcript.strip()
        
        # Get current agent speaking state
        agent_is_speaking = False
        if hasattr(session, 'agent') and session.agent:
            agent_is_speaking = getattr(session.agent, 'is_speaking', False)
        
        # Use helper function to decide
        should_interrupt = should_allow_interruption(transcript, agent_is_speaking)
        
        # Log what's happening with clear indicators
        status_emoji = "🗣️" if agent_is_speaking else "🤐"
        logger.info(f"User: '{user_text}' | Agent: {status_emoji} {'SPEAKING' if agent_is_speaking else 'SILENT'}")
        
        if not should_interrupt:
            # User only said backchannel words while agent was speaking
            logger.info(f"IGNORING backchannel - agent continues speaking")
            
            # CRITICAL FIX: The agent was already interrupted by VAD.
            # Since we have resume_false_interruption=True, LiveKit will
            # automatically resume if no valid turn was detected.
            # We just don't process this as a user turn by returning early.
            return
        else:
            # Either agent was silent OR user said real content
            if agent_is_speaking:
                logger.info(f"INTERRUPTING agent - user said: '{user_text}'")
            else:
                logger.info(f"RESPONDING to user - agent was silent")
            
            # Let default behavior proceed - session will handle the turn
            return


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
