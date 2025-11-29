"""
Test Agent with FREE API Options

This version uses completely free API services so you can test without paid keys.

Supported Free LLMs:
1. Groq (Recommended - fastest free option)
2. Google Gemini (Good quality, free)
3. Together AI (Free tier)

Just set the appropriate API key in .env file.
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
    cli,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero, groq

logger = logging.getLogger("test-interrupt-free")
logger.setLevel(logging.DEBUG)

load_dotenv()


# Detect which LLM to use based on available API keys
def create_llm():
    """Auto-detect which free LLM to use based on available API keys."""
    
    if os.getenv("GROQ_API_KEY"):
        logger.info("🎯 Using GROQ (FREE) - Fastest & Most Stable!")
        return groq.LLM(
            model="llama-3.1-8b-instant",  # Most stable free model, works reliably
            api_key=os.getenv("GROQ_API_KEY"),
        )
    
    elif os.getenv("GOOGLE_API_KEY"):
        logger.info("🎯 Using GOOGLE GEMINI (FREE)")
        return "google/gemini-2.0-flash-exp"
    
    elif os.getenv("TOGETHER_API_KEY"):
        logger.info("🎯 Using TOGETHER AI (FREE)")
        return "together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    
    elif os.getenv("OPENAI_API_KEY"):
        logger.info("🎯 Using OPENAI (Paid)")
        return "openai/gpt-4o-mini"
    
    else:
        logger.error("❌ No LLM API key found!")
        logger.error("Please add one of these to your .env file:")
        logger.error("  - GROQ_API_KEY (Recommended - Free & Fast)")
        logger.error("  - GOOGLE_API_KEY (Free)")
        logger.error("  - TOGETHER_API_KEY (Free)")
        logger.error("  - OPENAI_API_KEY (Paid)")
        raise ValueError("No LLM API key configured")


class TestAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful voice assistant for testing interruption handling. "
                "Greet the user warmly and have natural conversations with them. "
                "When asked to explain something, give detailed responses so we can test interruptions. "
                "Keep responses natural and conversational. "
                "Do not use emojis or markdown."
            )
        )

    async def on_enter(self):
        """Greet the user and offer to help."""
        self.session.generate_reply()


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Entry point with FREE API services."""
    ctx.log_context_fields = {"room": ctx.room.name}
    
    # Auto-detect which LLM to use
    llm_inst = create_llm()
    
    # Detect STT
    if os.getenv("DEEPGRAM_API_KEY"):
        stt_model = "deepgram/nova-3"
        logger.info("✅ STT: Deepgram (Free tier)")
    elif os.getenv("GOOGLE_API_KEY"):
        stt_model = "google"
        logger.info("✅ STT: Google Speech (Free tier)")
    else:
        logger.warning("⚠️ No STT key found - using first available")
        stt_model = "deepgram/nova-3"
    
    # Detect TTS
    if os.getenv("CARTESIA_API_KEY"):
        tts_model = "cartesia/sonic-2"
        logger.info("✅ TTS: Cartesia")
    elif os.getenv("ELEVENLABS_API_KEY"):
        tts_model = "elevenlabs/eleven_turbo_v2"
        logger.info("✅ TTS: ElevenLabs (Free tier: 10k chars/month)")
    elif os.getenv("GOOGLE_API_KEY"):
        tts_model = "google"
        logger.info("✅ TTS: Google Text-to-Speech (Free tier)")
    else:
        logger.warning("⚠️ No TTS key found - using first available")
        tts_model = "cartesia/sonic-2"
    
    # Create session with intelligent interruption handling
    session = AgentSession(
        stt=stt_model,
        llm=llm_inst,  # Auto-detected free LLM instance
        tts=tts_model,
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        allow_interruptions=True,
        min_interruption_duration=0.3,
        min_interruption_words=0,
        
        # 🎯 INTELLIGENT INTERRUPTION HANDLING
        # Comprehensive list of backchannel words (words users say to show they're listening)
        # These will be IGNORED when agent is speaking, but RESPONDED to when agent is silent
        # Note: Only unambiguous backchannels are included to avoid false positives
        backchannel_words=[
            # Affirmative backchannels
            'yeah', 'yay', 'yes', 'yep', 'yup', 'ya', 'yea',
            # OK variations (FIXED: added 'okay' which was missing!)
            'ok', 'okay', 'k', 'kay',
            # Thinking/listening sounds
            'hmm', 'hm', 'mm', 'mmm', 'mhm',
            # Agreement indicators  
            'right', 'alright', 'sure',
            # Acknowledgment sounds (only unambiguous ones)
            'aha', 'ah', 'oh', 'ooh', 'uh',
        ],
    )
    
    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        logger.info(f"[AGENT STATE] {ev.old_state} -> {ev.new_state}")
    
    @session.on("user_state_changed")
    def _on_user_state_changed(ev):
        logger.info(f"[USER STATE] {ev.old_state} -> {ev.new_state}")
    
    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev):
        if ev.is_final:
            logger.info(f"[TRANSCRIPT] {ev.transcript}")

    await session.start(
        agent=TestAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(server)

