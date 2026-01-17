import logging
import asyncio
from typing import Set
from enum import Enum
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
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# --- CONFIGURATION ---
try:
    from config import IGNORE_WORDS, INTERRUPT_WORDS, VERBOSE_LOGGING
except ImportError:
    IGNORE_WORDS = {
        'yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'right', 'aha', 'mhm', 'mm-hmm', 
        'sure', 'yep', 'yes', 'got it', 'i see', 'understand', 'alright', 'cool', 'nice'
    }
    INTERRUPT_WORDS = {
        'wait', 'stop', 'no', 'hold', 'pause', 'hang on', 'hold on', 
        'one moment', 'actually', 'but', 'however'
    }
    VERBOSE_LOGGING = True

logger = logging.getLogger("intelligent-agent")
if VERBOSE_LOGGING:
    logger.setLevel(logging.INFO)

load_dotenv()

class AgentState(Enum):
    IDLE = "idle"
    SPEAKING = "speaking"

class InterruptionGuard:
    def __init__(self, ignore_words: Set[str], interrupt_words: Set[str]):
        self.ignore_words = ignore_words
        self.interrupt_words = interrupt_words
        self.agent_state = AgentState.IDLE

    def should_interrupt(self, text: str) -> bool:
        """
        Returns TRUE if we should stop the agent.
        Returns FALSE if we should ignore the user.
        """
        if not text or not text.strip():
            return False
            
        clean_text = text.lower().strip('. ,!?')
        words = clean_text.split()
        
        # 1. PRIORITY: If a command word exists, INTERRUPT IMMEDIATELY.
        if any(w in clean_text for w in self.interrupt_words):
            return True
            
        # 2. IGNORE: If the text is ONLY backchannel words, DO NOT INTERRUPT.
        if all(w in self.ignore_words for w in words):
            return False
            
        # 3. DEFAULT: If it's a real sentence (e.g. "I have a question"), INTERRUPT.
        return True

class MyAgent(Agent):
    def __init__(self, guard: InterruptionGuard) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Do NOT stop speaking if the user says 'yeah' or 'okay'. "
                "Only stop if they explicitly ask you to wait or stop."
            )
        )
        self.guard = guard

    async def on_enter(self):
        # When idle, allow VAD to work normally so we respond to "Hey"
        self.guard.agent_state = AgentState.IDLE
        self.allow_interruptions = True
        await self.session.generate_reply()

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    
    guard = InterruptionGuard(IGNORE_WORDS, INTERRUPT_WORDS)
    
    session = AgentSession(
        stt="deepgram/nova-3", 
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
    )

    agent = MyAgent(guard)

    # ------------------------------------------------------------------
    #  LOGIC: HOW TO HANDLE "STOP" WHILE IGNORING "YEAH"
    # ------------------------------------------------------------------

    @session.on("agent_started_speaking")
    def _on_agent_started_speaking():
        guard.agent_state = AgentState.SPEAKING
        
        # 1. DISABLE VAD: This prevents the instant pause on "Yeah".
        # The agent is now "deaf" to noise, but STT is still running!
        agent.allow_interruptions = False 
        
        logger.info("🗣️ AGENT SPEAKING: VAD Disabled (Waiting for STT commands)")

    @session.on("agent_stopped_speaking")
    def _on_agent_stopped_speaking():
        guard.agent_state = AgentState.IDLE
        
        # 2. ENABLE VAD: When silent, we must hear everything (even "Yeah").
        agent.allow_interruptions = True
        
        logger.info("🤐 AGENT STOPPED: VAD Enabled")

    @session.on("user_transcript_updated")
    def _on_user_transcript_updated(transcript):
        """
        This runs continuously in the background.
        Even if allow_interruptions=False, we still receive this text!
        """
        # If we are already listening (IDLE), let the system handle it naturally.
        if agent.allow_interruptions is True:
            return

        if not transcript.text:
            return
            
        partial_text = transcript.text
        
        # Check if the user said a "Stop" word or a real sentence
        if guard.should_interrupt(partial_text):
            logger.info(f"🛑 COMMAND DETECTED: '{partial_text}'")
            
            # --- THE TRICK TO MAKE "STOP" WORK ---
            
            # A. Re-enable interruptions so the system accepts the turn
            agent.allow_interruptions = True
            
            # B. MANUALLY interrupt the current speech immediately
            # This cuts off the audio instantly, just like VAD would.
            if hasattr(agent, 'interrupt'):
                asyncio.create_task(agent.interrupt())
        else:
            # If it's just "Yeah", we do nothing. 
            # allow_interruptions stays False. Audio continues perfectly.
            pass

    @session.on("user_speech_committed")
    def _on_user_speech_committed(msg):
        # Reset to listening mode after any full turn
        if guard.agent_state == AgentState.IDLE:
            agent.allow_interruptions = True

    await session.start(agent=agent, room=ctx.room)

if __name__ == "__main__":
    cli.run_app(server)