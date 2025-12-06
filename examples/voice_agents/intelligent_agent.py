"""
Intelligent Interruption Agent Demo

Uses Gemini (LLM) + Deepgram (STT/TTS) + Silero (VAD)

Run with: python intelligent_agent.py start (for cloud)
Run with: python intelligent_agent.py dev (for local)
"""

import logging
from dotenv import load_dotenv

from livekit.agents import (
    AgentSession,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
)
from livekit.plugins import silero, google, deepgram

# Import from the livekit package structure
from livekit.agents.voice.interrupt_handler import InterruptHandler, AgentState

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("intelligent-agent")

load_dotenv()


def prewarm(proc: JobProcess):
    """Prewarm VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("✓ VAD model prewarmed")


async def entrypoint(ctx: JobContext):
    """
    Main entry point for the agent session.
    
    Stack:
    - STT: Deepgram
    - LLM: Google Gemini 2.0 Flash
    - TTS: Deepgram
    - VAD: Silero (local)
    """
    logger.info(f"🚀 Starting session in room: {ctx.room.name}")
    
    # Initialize interrupt handler
    interrupt_handler = InterruptHandler()
    agent_state = AgentState.SILENT
    
    # Create the agent session
    session = AgentSession(
        stt=deepgram.STT(
            model="nova-2",
            language="en-US",
        ),
        
        llm=google.LLM(
            model="gemini-2.0-flash-exp",
            temperature=0.7,
        ),
        
        tts=deepgram.TTS(
            model="aura-asteria-en",
        ),
        
        vad=ctx.proc.userdata["vad"],
    )
    
    # Track agent state
    @session.on("agent_speech_started")
    def on_speech_start():
        nonlocal agent_state
        agent_state = AgentState.SPEAKING
        logger.info("🗣️  Agent started speaking")
    
    @session.on("agent_speech_stopped")
    def on_speech_stop():
        nonlocal agent_state
        agent_state = AgentState.SILENT
        logger.info("🤐 Agent stopped speaking")
    
    # Hook user speech for filtering
    @session.on("user_speech_committed")
    def on_user_speech(text: str):
        """Apply intelligent interruption filtering."""
        logger.info(f"👤 User said: '{text}' (agent_state={agent_state.value})")
        
        should_interrupt = interrupt_handler.should_interrupt(agent_state, text)
        
        if not should_interrupt and agent_state == AgentState.SPEAKING:
            logger.info(f"Filtering filler: '{text}' - agent continues")
            return
        else:
            logger.info(f"Processing input: '{text}'")
    
    # Start session
    await session.start(room=ctx.room, participant=ctx.participant)
    
    # Generate initial greeting
    await session.say("Hello! I'm your AI assistant with smart interruption handling. I can tell the difference between filler words like 'yeah' or 'okay' and real commands like 'stop' or 'wait'. Try talking to me and see how it works!")
    
    logger.info("Session started - agent is ready")
    
    # Keep alive
    await session.aclose()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="intelligent-interruption-agent", 
        )
    )

