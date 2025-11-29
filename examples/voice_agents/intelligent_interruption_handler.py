import asyncio
import logging
import re
from typing import List, Set

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.agents.voice import SpeechHandle
from livekit.plugins import cartesia, deepgram, openai, silero

logger = logging.getLogger("intelligent-interruption-handler")

load_dotenv()


class IntelligentInterruptionHandler:
    """
    Handles intelligent interruption logic based on agent state and user input.
    
    This class distinguishes between passive acknowledgments (like "yeah", "ok", "hmm")
    and active interruptions (like "wait", "stop", "no") based on whether the agent
    is currently speaking or silent.
    """
    
    def __init__(self, session: AgentSession):
        self.session = session
        self.ignore_list: Set[str] = {'yeah', 'ok', 'hmm', 'right', 'uh-huh', 'yep', 'yup', 'aha'}
        self.interrupt_list: Set[str] = {'wait', 'stop', 'no', 'cancel', 'hold on'}
        
    def should_ignore_input(self, text: str, agent_speaking: bool) -> bool:
        """
        Determines if user input should be ignored based on agent state and input content.
        
        Args:
            text: The user's transcribed input
            agent_speaking: Whether the agent is currently speaking
            
        Returns:
            True if the input should be ignored, False otherwise
        """
        normalized_text = self._normalize_text(text)
        
        if not agent_speaking:
            return False
            
        words = normalized_text.split()
        
        if len(words) == 1 and words[0] in self.ignore_list:
            return True
            
        for word in words:
            if word in self.interrupt_list:
                return False
                
        all_passive = all(word in self.ignore_list for word in words)
        return all_passive and agent_speaking
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison by lowercasing and removing punctuation."""
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = ' '.join(normalized.split())
        return normalized


class IntelligentAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You are a helpful assistant who responds to user queries."
            "Keep your responses concise and to the point."
            "Do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "You will speak English to the user.",
        )
        self.interruption_handler: IntelligentInterruptionHandler | None = None

    def set_interruption_handler(self, handler: IntelligentInterruptionHandler) -> None:
        self.interruption_handler = handler

    async def on_user_input_transcribed(self, text: str) -> None:
        """
        Called when user input is transcribed. Apply intelligent interruption logic here.
        """
        if self.interruption_handler is None:
            return
            
        agent_speaking = self.session.agent_state == "speaking"
        
        should_ignore = self.interruption_handler.should_ignore_input(text, agent_speaking)
        
        logger.info(
            f"User input: '{text}', Agent speaking: {agent_speaking}, "
            f"Should ignore: {should_ignore}"
        )
        
        if should_ignore and agent_speaking:
            logger.info(f"Ignoring passive acknowledgment: '{text}' while agent is speaking")


server = AgentServer()


def prewarm(proc):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection="vad",
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        allow_interruptions=True,
    )

    agent = IntelligentAgent()
    interruption_handler = IntelligentInterruptionHandler(session)
    agent.set_interruption_handler(interruption_handler)

    await session.start(
        agent=agent,
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)