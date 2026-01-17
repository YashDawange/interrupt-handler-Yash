import asyncio
import logging
from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import openai, silero

from interrupt_handler import InterruptionHandler
from config import IGNORE_WORDS, DEBUG_MODE

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntelligentVoiceAssistant(VoiceAssistant):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interrupt_handler = InterruptionHandler(ignore_words=IGNORE_WORDS)
        self._is_speaking = False
        logger.info("IntelligentVoiceAssistant initialized")
    
    async def _on_agent_speech_started(self):
        self._is_speaking = True
        self.interrupt_handler.set_agent_speaking(True)
        logger.debug("Agent started speaking")
    
    async def _on_agent_speech_ended(self):
        self._is_speaking = False
        self.interrupt_handler.set_agent_speaking(False)
        logger.debug("Agent stopped speaking")
    
    async def _process_user_speech(self, text):
        should_interrupt = self.interrupt_handler.should_interrupt(text)
        
        if not should_interrupt:
            logger.info(f"Ignoring: '{text}'")
            return False
        
        logger.info(f"Processing: '{text}'")
        return True


async def entrypoint(ctx: JobContext):
    logger.info(f"Starting agent for room: {ctx.room.name}")
    
    initial_ctx = llm.ChatContext().append(
        role="system",
        text=(
            "You are a helpful AI assistant. When users give feedback like "
            "'yeah', 'ok', or 'hmm' while you're speaking, continue your "
            "explanation naturally. Only stop when they ask you to stop or "
            "give a clear command."
        ),
    )
    
    assistant = IntelligentVoiceAssistant(
        vad=silero.VAD.load(),
        stt=openai.STT(),
        llm=openai.LLM(),
        tts=openai.TTS(),
        chat_ctx=initial_ctx,
    )
    
    @assistant.on("agent_speech_started")
    def on_speech_started():
        asyncio.create_task(assistant._on_agent_speech_started())
    
    @assistant.on("agent_speech_ended")
    def on_speech_ended():
        asyncio.create_task(assistant._on_agent_speech_ended())
    
    @assistant.on("user_speech_committed")
    def on_user_speech(msg):
        text = msg.text if hasattr(msg, 'text') else str(msg)
        
        should_process = asyncio.run(
            assistant._process_user_speech(text)
        )
        
        if not should_process:
            return False
    
    assistant.start(ctx.room)
    
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    logger.info("Agent ready")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
