import asyncio
import logging
import string
from enum import Enum

logger = logging.getLogger(__name__)

class AgentState(Enum):
    IDLE = "idle"
    SPEAKING = "speaking"

class InterruptionHandler:
    def __init__(self, state_ref):
        
        self.state_ref = state_ref
        self._lock = asyncio.Lock()

        self.INTERRUPT_WORDS = {"stop", "wait", "cancel", "pause", "quit", "exit", "no"}
        self.FILLERS = {"ok", "okay", "yeah", "yep", "uh", "um", "hmm", "right", "alright"}

   
    def mark_agent_speaking(self):
        if self.state_ref["state"] != AgentState.SPEAKING:
            self.state_ref["state"] = AgentState.SPEAKING
            logger.info("Agent state → SPEAKING")

    def mark_agent_idle(self):
        if self.state_ref["state"] != AgentState.IDLE:
            self.state_ref["state"] = AgentState.IDLE
            logger.info(" Agent state → IDLE")

  
    def _normalize(self, text: str):
        text = text.lower().translate(str.maketrans("", "", string.punctuation))
        return text.split()

    def is_filler(self, text: str) -> bool:
        words = self._normalize(text)
        return words and all(w in self.FILLERS for w in words)


    async def should_interrupt(self, transcript: str) -> bool:
        async with self._lock:
            words = self._normalize(transcript)
            state = self.state_ref["state"]
            logger.debug(f"AgentState={state}")

            if not words:
                return False


            if any(w in self.INTERRUPT_WORDS for w in words):
                logger.info("Explicit interrupt")
                return True


            if state == AgentState.SPEAKING:
                if self.is_filler(transcript):
                    logger.info("Ignored filler while speaking")
                    return False
                logger.info("Interrupt while speaking")
                return True


            logger.info("Agent idle → allow")
            return True
