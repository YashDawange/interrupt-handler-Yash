import os
import logging
from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env.local")

# --- LOGGING SETUP ---
logger = logging.getLogger("assignment-logic")
logger.setLevel(logging.INFO)

# --- MODULAR CONFIGURATION ---
# Robust list handling: splits by comma and strips whitespace
env_ignored = os.getenv("IGNORED_WORDS", "yeah,ok,okay,hmm,aha,uh-huh,right,yup,yep,sure,correct,gotcha,i see").lower()
IGNORED_WORDS = [w.strip() for w in env_ignored.split(",")]

class AssignmentAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a context-aware Voice Assistant designed for a strict university assignment.
            
            # CRITICAL RULES
            1. WHEN SPEAKING: Ignore backchannel words (Yeah, Ok, Hmm, Right). Do NOT pause. Keep talking.
            2. WHEN SPEAKING: Stop IMMEDIATELY if the user says "Stop", "Wait", or "No".
            3. WHEN SILENT: Respond to "Yeah" or "Ok" as a normal conversation turn.
            
            # PERSONALITY
            Professional, precise, and concise (1-3 sentences). No special formatting.
            """
        )

server = AgentServer()

@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    # --- YOUR REQUESTED STRUCTURE (UNCHANGED) ---
    session = AgentSession(
        stt="deepgram/nova-2:en-IN",          # Your requested model string
        llm="openai/gpt-4o-mini",             # Your requested model string
        tts="deepgram/aura-2:athena",         # Your requested model string
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    # --- THE STRICT LOGIC LAYER ---
    @session.on("user_speech_committed")
    def _on_user_speech_committed(msg: rtc.TranscriptionSegment):
        # 1. Clean the text (handle "Ok, ok" or "Yeah!")
        user_text = msg.text.lower().strip().replace(".", "").replace(",", "").replace("!", "").replace("?", "")
        words = user_text.split()
        
        # 2. Check Context: IS THE AGENT SPEAKING?
        if session.is_speaking:
            # 3. Strict Filler Check: Are ALL words in the ignore list?
            # This handles "Ok ok" or "Yeah right" correctly
            is_pure_filler = all(word in IGNORED_WORDS for word in words)
            
            if is_pure_filler:
                # ACTION: IGNORE. 
                # Since allow_interruptions=False, the agent will just keep talking.
                logger.info(f"Context: [SPEAKING] | Input: '{user_text}' -> ACTION: IGNORE (No Hiccup)")
                return 
            else:
                # ACTION: INTERRUPT.
                # User said something active like "Stop" or a question.
                logger.info(f"Context: [SPEAKING] | Input: '{user_text}' -> ACTION: INTERRUPT (Active Command)")
                session.interrupt()
        
        else:
            # Context: SILENT. 
            # Agent will process this normally.
            logger.info(f"Context: [SILENT] | Input: '{user_text}' -> ACTION: RESPOND")

    # Start the agent (BVC is safe for your environment)
    await session.start(
        room=ctx.room,
        agent=AssignmentAgent(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVC(),
            ),
        ),
    )

    # --- THE CRITICAL FIX ---
    # allow_interruptions=False disables the "hiccup".
    # The agent will ONLY stop if your logic above calls session.interrupt().
    await session.generate_reply(
        instructions="Introduce yourself with a long, detailed sentence about how robust your logic is. Explicitly ask the user to say 'Right' or 'Yep' while you are talking to prove you won't stop.",
        allow_interruptions=False 
    )

if __name__ == "__main__":
    agents.cli.run_app(server)