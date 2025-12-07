import logging
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from livekit.agents import (
    Agent, AgentServer, AgentSession, JobContext, 
    JobProcess, cli, llm, WorkerOptions
)
from livekit.plugins import deepgram, groq, cartesia, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# --- IMPORT THE LOGIC MODULE ---
# This assumes logic.py is in the same folder as basic_agent.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from logic import InterruptHandler, AgentState, Action

# --- SETUP ---
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)

logger = logging.getLogger("kelly-agent")

# --- AGENT PERSONA ---
class KellyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "Your name is Kelly. You are testing interruption logic. "
                "You must read long explanations about history or science. "
                "Speak for at least 30 seconds uninterrupted. "
                "Do not use emojis."
            )
        )

    async def on_enter(self):
        # Initial Greeting
        await self.session.generate_reply()

# --- SERVER & ENTRYPOINT ---
server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # 1. Initialize Logic Engine
    handler = InterruptHandler()  # Loads from interrupt_config.json automatically
    
    # 2. Configure Session
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        # tts=deepgram.TTS(),
        tts=cartesia.TTS(voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
        
        # KEY CONFIGURATION for "False Start" Handling
        # We need a large buffer (1.0s) so our logic has time to process "Yeah"
        # [cite_start]before the agent commits to stopping. [cite: 47-49]
        resume_false_interruption=True, 
        false_interruption_timeout=1.0, 
        min_interruption_words=1,
        min_interruption_duration=0.1,
    )

    # 3. Create the Event Listener for Logic Execution
    @session.on("user_input_transcribed")
    def on_user_input(ev):
        text = ev.transcript
        
        # Determine State: Check if audio is currently playing
        is_speaking = False
        try:
             if session.response and session.response.audio:
                 # Check if the audio source is actually playing or paused
                 # (Implementation varies by SDK version, checking existence is a safe start)
                 is_speaking = True
        except:
            pass
            
        current_state = AgentState.SPEAKING if is_speaking else AgentState.SILENT
        
        # DECIDE ACTION
        action = handler.decide_action(current_state, text)
        
        logger.info(f"Input: '{text}' | State: {current_state} | Action: {action.value}")

        # EXECUTE ACTION
        if action == Action.IGNORE_AND_RESUME:
            # A. Clear the turn so LLM doesn't reply
            if hasattr(session, 'clear_user_turn'):
                session.clear_user_turn()
            
            # B. Force Resume Audio
            # This cancels the "false interruption" caused by VAD
            try:
                if session.response.audio.can_pause:
                    session.response.audio.resume()
            except:
                pass
                
        elif action == Action.INTERRUPT:
            # Standard behavior: VAD has already paused it, STT confirmed it. 
            # We let the event pass through to the LLM.
            pass
            
        elif action == Action.RESPOND:
            # Standard behavior: Agent was silent, so this is a normal turn.
            pass

    # 4. Start the Agent
    await session.start(agent=KellyAgent(), room=ctx.room)

if __name__ == "__main__":
    cli.run_app(server)