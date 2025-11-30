from dotenv import load_dotenv  

load_dotenv()

import logging
from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import deepgram, silero
from livekit.plugins import groq  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Words to ignore when agent is speaking
BACKCHANNEL_WORDS = {'yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'mhm', 'right', 'aha', 'yep'}

# Words that should always interrupt
INTERRUPT_WORDS = {'wait', 'stop', 'no', 'hold', 'pause', 'but'}


class SmartAgent:
    
    def __init__(self):
        self.is_speaking = False
        
    def should_ignore_input(self, text: str) -> bool:
        # If agent is not speaking, process everything
        if not self.is_speaking:
            logger.info(f"Agent silent, processing: '{text}'")
            return False
        
        # Agent IS speaking - apply smart filtering
        words = text.lower().split()
        
        # Check for interrupt words first
        has_interrupt = any(word in INTERRUPT_WORDS for word in words)
        if has_interrupt:
            logger.info(f"Interrupt word found in '{text}' - stopping agent")
            return False
        
        # Check if ALL words are backchannel words
        only_backchannel = all(word in BACKCHANNEL_WORDS for word in words)
        if only_backchannel:
            logger.info(f"Backchannel only '{text}' - ignoring, agent continues")
            return True
        
        # Mixed input or unknown words - allow interruption for safety
        logger.info(f"Mixed input '{text}' - allowing interruption")
        return False


async def entrypoint(ctx: JobContext):    
    # Create our smart agent
    smart_agent = SmartAgent()
    
    # Connect to room
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")
    
    # Use the newer Agent and AgentSession API
    from livekit.agents import Agent, AgentSession
    
    # Create the base agent
    agent = Agent(
        instructions=(
            "You are a helpful voice assistant. "
            "Keep your responses clear and concise. "
            "Speak naturally like you're having a conversation."
        )
    )
    
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),  
        tts=deepgram.TTS(model="aura-asteria-en"),   
        allow_interruptions=True,
        min_interruption_duration=0.3,
    )
    
    # Track when agent speaks
    @session.on("agent_speech_created")
    def on_speech_started(event):
        smart_agent.is_speaking = True
        logger.info("🗣️  Agent started speaking")
    
    @session.on("agent_speech_committed")
    def on_speech_committed(event):
        smart_agent.is_speaking = False
        logger.info("Agent stopped speaking (committed)")
    
    @session.on("agent_speech_interrupted")
    def on_speech_interrupted(event):
        smart_agent.is_speaking = False
        logger.info("Agent stopped speaking (interrupted)")
    
    #user speech
    @session.on("user_speech_committed")
    def on_user_speech(event):
        user_text = event.item.text_content
        
        # Check if we should ignore this input
        if smart_agent.should_ignore_input(user_text):
            logger.info(f"Ignoring input, agent continues")
        else:
            logger.info(f"Processing input: '{user_text}'")
    
    # session start
    await session.start(agent=agent, room=ctx.room)
    
    logger.info("Agent is ready!")
    
    await session.generate_reply(
        instructions="Greet the user warmly and ask how you can help them today."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))