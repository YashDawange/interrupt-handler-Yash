"""
Intelligent Interruption Agent Demo
"""

import logging
import os
from dotenv import load_dotenv



from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
)
from livekit.plugins import silero, google, deepgram, openai
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
    logger.info(f"🚀 Starting session in room: {ctx.room.name}")

    # 1. Connect to the room
    await ctx.connect()

    # 2. Initialize the Agent object
    # FIXED: Removed 'name', only kept 'instructions'
    agent = Agent(
        instructions="""You are a helpful AI assistant.
        
        IMPORTANT INTERRUPTION HANDLING:
        - If the user says "stop", "wait", or "hold on", STOP speaking immediately and acknowledge with a single word like "Okay" or "Stopped". Do NOT explain that you are stopping.
        - If the user interrupts with a question, answer it directly and concisely.
        - Keep your responses natural and conversational, but concise when interrupted.
        """
    )

    # 3. Initialize interrupt handler & state
    interrupt_handler = InterruptHandler()
    agent_state = AgentState.SILENT


    # 4. Create session - block short utterances, manually handle interrupts
    # Using Groq for fast, free LLM inference
    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en-US", interim_results=True),
        llm=openai.LLM(
            model="llama-3.1-8b-instant",
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.7,
        ),
        tts=deepgram.TTS(model="aura-asteria-en"),
        vad=ctx.proc.userdata["vad"],
        allow_interruptions=True,
        min_interruption_words=5,  # Block single-word utterances like "yeah"
        min_interruption_duration=0.3,  # Faster response
    )
    
    # Track state
    pending_interrupt_check = False

    # 5. Event handlers
    @session.on("agent_state_changed")
    def on_agent_state_change(event):
        """Track agent state"""
        nonlocal agent_state, pending_interrupt_check
        if event.new_state == "speaking":
            agent_state = AgentState.SPEAKING
            pending_interrupt_check = False
            logger.info("🗣️  Agent started speaking")
        elif event.old_state == "speaking":
            agent_state = AgentState.SILENT
            logger.info("🤐 Agent stopped speaking")

    @session.on("user_input_transcribed")
    def on_user_transcript(event):
        """Monitor transcripts and manually trigger interrupts for valid words"""
        nonlocal pending_interrupt_check
        
        transcript_text = event.transcript.lower().strip()
        if not transcript_text:
            return
        
        # Check interim transcripts for manual interrupt triggering
        if not event.is_final and agent_state == AgentState.SPEAKING:
            logger.info(f"👂 Interim: '{transcript_text}'")
            
            # Check if this should trigger an interrupt
            should_interrupt = interrupt_handler.should_interrupt(agent_state, transcript_text)
            
            if should_interrupt and not pending_interrupt_check:
                logger.info(f"⚡ Valid interrupt word detected: '{transcript_text}' - manually triggering")
                pending_interrupt_check = True
                try:
                    session.interrupt()
                except Exception as e:
                    logger.warning(f"Failed to manually interrupt: {e}")
            elif not should_interrupt:
                logger.info(f"🚫 Filler word detected: '{transcript_text}' - blocking via min_interruption_words")
        
        # Handle final transcripts
        elif event.is_final:
            logger.info(f"👤 Final: '{transcript_text}'")
            pending_interrupt_check = False
            
            # Check what happened
            should_interrupt = interrupt_handler.should_interrupt(agent_state, transcript_text)
            if not should_interrupt:
                logger.info(f"✅ Filler word successfully blocked")
            else:
                logger.info(f"✅ Valid interruption processed")



    # 6. Start the session
    await session.start(agent=agent, room=ctx.room)

    # 7. Greet
    await session.say(
        "Hello! I'm your AI assistant. Go ahead, ask me anything!"
    )

    logger.info("✅ Session started - agent is ready")

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="intelligent-interruption-agent", 
        )
    )