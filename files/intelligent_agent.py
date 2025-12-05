"""
Intelligent Agent with Context-Aware Interruption Handling
"""

import logging
from typing import Optional
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from interrupt_handler import (
    IntelligentInterruptHandler,
    create_interrupt_config_from_env
)

logger = logging.getLogger("intelligent-agent")
logger.setLevel(logging.INFO)

load_dotenv()


class IntelligentAgent(Agent):
    """Agent with intelligent interruption handling"""
    
    def __init__(self, interrupt_handler: IntelligentInterruptHandler):
        super().__init__(
            instructions=(
                "You are a helpful AI assistant named Alex. "
                "When explaining things, provide detailed and thorough explanations. "
                "Don't worry if the user says 'yeah', 'ok', or 'hmm' while you're talking - "
                "these are just acknowledgments that they're listening. "
                "Continue speaking naturally through these backchannels. "
                "However, if they say 'stop', 'wait', or 'no', stop immediately and listen. "
                "Keep your responses conversational and engaging."
            )
        )
        self.interrupt_handler = interrupt_handler
        logger.info("IntelligentAgent initialized")
    
    async def on_enter(self):
        """Called when agent enters the session"""
        logger.info("Agent entering session")
        self.session.generate_reply(
            instructions=(
                "Greet the user warmly. Introduce yourself as Alex. "
                "Offer to explain something interesting or tell them a story. "
                "Be friendly and conversational."
            )
        )
    
    @function_tool
    async def tell_story(self, context: RunContext, topic: str = "artificial intelligence"):
        """
        Tell a detailed story about a topic.
        Perfect for testing interruption handling with long responses.
        
        Args:
            topic: The topic to tell a story about (default: artificial intelligence)
        """
        logger.info(f"Telling story about: {topic}")
        
        return (
            f"Let me tell you a fascinating story about {topic}. "
            "This is a detailed explanation that will take some time to deliver. "
            "I'll be speaking for a while, which makes it perfect for testing "
            "how the system handles user feedback like 'yeah' or 'hmm' during my explanation. "
            "The story continues with many interesting details and facts that demonstrate "
            "the ability to maintain a natural flow even when the user acknowledges they're listening."
        )
    
    @function_tool
    async def explain_concept(
        self, 
        context: RunContext, 
        concept: str,
        detail_level: str = "detailed"
    ):
        """
        Explain a concept in detail.
        
        Args:
            concept: The concept to explain
            detail_level: Level of detail - 'brief' or 'detailed'
        """
        logger.info(f"Explaining concept: {concept} (detail level: {detail_level})")
        
        if detail_level == "detailed":
            return (
                f"I'll give you a comprehensive explanation of {concept}. "
                "This will be thorough and take some time, so feel free to say 'yeah' "
                "or 'ok' to let me know you're following along. Those won't interrupt me. "
                "If you need me to stop or wait, just say so."
            )
        else:
            return f"Here's a brief overview of {concept}."


# Global agent server
server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm resources before handling jobs"""
    logger.info("Prewarming resources...")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD loaded and ready")


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entry point for the agent session"""
    
    logger.info(f"Starting new session in room: {ctx.room.name}")
    
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "participant": "intelligent-agent"
    }
    
    # Create interrupt handler with environment config
    config = create_interrupt_config_from_env()
    interrupt_handler = IntelligentInterruptHandler(config)
    
    logger.info(f"Interrupt handler configured:")
    logger.info(f"  - Ignore words: {config.ignore_words}")
    logger.info(f"  - Interrupt words: {config.interrupt_words}")
    
    # Create agent session
    session = AgentSession(
        # Use string syntax for provider/model
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # Enable preemptive generation for faster responses
        preemptive_generation=True,
        # CRITICAL: Disable automatic false interruption resumption
        # We handle this ourselves with intelligent logic
        resume_false_interruption=False,
        false_interruption_timeout=0.5,
    )
    
    # Track agent speaking state
    @session.on("agent_speech_started")
    def on_agent_speech_started():
        """Track when agent starts speaking"""
        interrupt_handler.set_agent_speaking(True)
        logger.debug("🗣️  Agent started speaking")
    
    @session.on("agent_speech_stopped")  
    def on_agent_speech_stopped():
        """Track when agent stops speaking"""
        interrupt_handler.set_agent_speaking(False)
        logger.debug("🔇 Agent stopped speaking")
    
    # Create the agent
    agent = IntelligentAgent(interrupt_handler)
    
    # Start the session
    logger.info("Starting agent session...")
    await session.start(agent=agent, room=ctx.room)
    
    logger.info("Agent session started successfully")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("="*60)
    logger.info("INTELLIGENT INTERRUPTION HANDLER AGENT")
    logger.info("="*60)
    
    # Run the agent
    cli.run_app(server)
