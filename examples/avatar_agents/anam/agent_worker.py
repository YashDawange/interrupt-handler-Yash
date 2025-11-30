import logging
import os
from typing import Set

from dotenv import load_dotenv

from livekit.agents import (
    Agent, 
    AgentServer, 
    AgentSession, 
    JobContext, 
    cli,
    llm  # <--- Added this import
)
from livekit.plugins import anam, openai

logger = logging.getLogger("anam-avatar-example")
logger.setLevel(logging.INFO)

load_dotenv()

server = AgentServer()

# --- [CONFIG] Ignore List ---
IGNORE_WORDS: Set[str] = {
    "yeah", "ok", "okay", "hmm", "mhmm", "aha", 
    "right", "sure", "yep", "uh-huh", "go on"
}

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="alloy",
            # --- CRITICAL CONFIGURATION ---
            # interrupt_response=False: Prevents OpenAI from auto-stopping the audio.
            # This ensures "Yeah" NEVER causes a stutter.
            turn_detection={
                "type": "server_vad", 
                "silence_duration_ms": 600, 
                "interrupt_response": False 
            }
        ),
        # We manually handle interruptions
        resume_false_interruption=False, 
    )

    # --- Anam Setup (Graceful Fallback) ---
    anam_api_key = os.getenv("ANAM_API_KEY")
    anam_avatar_id = os.getenv("ANAM_AVATAR_ID")
    
    if anam_api_key and anam_avatar_id:
        anam_avatar = anam.AvatarSession(
            persona_config=anam.PersonaConfig(name="avatar", avatarId=anam_avatar_id),
            api_key=anam_api_key,
        )
        await anam_avatar.start(session, room=ctx.room)
    else:
        logger.warning("⚠️ Anam keys missing. Avatar will not load (Voice-only mode).")

    # --- [LOGIC LAYER] ---

    # Corrected type hint: llm.ChatMessage instead of cli.ChatMessage
    @session.on("user_speech_committed")
    def on_user_speech(msg: llm.ChatMessage):
        # 1. Clean the text
        transcript = msg.content.strip().lower()
        clean_text = "".join(c for c in transcript if c.isalnum() or c.isspace())

        # 2. Check State: Is the agent currently speaking?
        is_agent_speaking = session.response_in_progress

        # If agent is silent, we behave normally
        if not is_agent_speaking:
            return

        # 3. LOGIC: Is this a backchannel?
        if clean_text in IGNORE_WORDS:
            logger.info(f"🚫 IGNORE: '{clean_text}' (Agent continues)")
            return 

        # 4. LOGIC: Is this a real command?
        # Manually stop the agent now.
        logger.info(f"✅ INTERRUPT: '{clean_text}'")
        session.interrupt()

    # --- Start ---
    await session.start(agent=Agent(instructions="Talk to me!"), room=ctx.room)
    session.generate_reply(instructions="Say hello.")

if __name__ == "__main__":
    cli.run_app(server)