import re
import asyncio
from enum import Enum
from typing import Set, Optional
from dataclasses import dataclass

class AgentState(Enum):
    SPEAKING = "speaking"
    WAITING = "waiting"
    IDLE = "idle"

@dataclass
class UtteranceClass:
    kind: str  
    text: str
    confidence: float = 1.0

class InterruptController:
    def __init__(self):
        self.state = AgentState.IDLE
        self.current_tts_handle = None
        self.pending_interrupt = None
        
        
        self.soft_tokens: Set[str] = set(os.getenv("SOFT_TOKENS", "yeah,ok,hmm,uh-huh,right,mm-hmm").lower().split(","))
        self.hard_tokens: Set[str] = set(os.getenv("HARD_TOKENS", "stop,wait,no,hold,pause").lower().split(","))
        self.max_soft_length = int(os.getenv("MAX_SOFT_LENGTH", "3"))
        
        self.pending_timeout = 0.2  

    def normalize(self, text: str) -> list[str]:
        
        text = re.sub(r'[^\w\s]', '', text.lower())
        words = text.split()
        
        ngrams = words.copy()
        for i in range(len(words)-1):
            ngrams.append(f"{words[i]} {words[i+1]}")
        return ngrams

    def classify(self, text: str) -> UtteranceClass:
        
        tokens = self.normalize(text)
        word_count = len(tokens)
        
        has_hard = any(t in self.hard_tokens for t in tokens)
        has_soft = any(t in self.soft_tokens for t in tokens)
        
        if has_hard:
            return UtteranceClass("HARD", text)
        elif has_soft and word_count <= self.max_soft_length:
            return UtteranceClass("SOFT_ONLY", text)
        else:
            return UtteranceClass("NORMAL", text)

    async def on_speech_start(self, tts_handle):
        self.state = AgentState.SPEAKING
        self.current_tts_handle = tts_handle

    def on_speech_end(self):
        self.state = AgentState.WAITING
        self.current_tts_handle = None
        if self.pending_interrupt:
            self.pending_interrupt = None

    async def on_user_speech(self, text: str, session):
        classification = self.classify(text)
        
        if self.state == AgentState.SPEAKING:
            if classification.kind == "SOFT_ONLY":
                print(f"[BACKCHANNEL] Ignored: {text}")
                return False  
            else:
                await session.interrupt()
                self.state = AgentState.IDLE
                return True  
        
        elif self.state == AgentState.WAITING:
            if classification.kind == "SOFT_ONLY":
                
                await session.say("Great, let’s continue.", allow_interruptions=False)
                self.state = AgentState.SPEAKING
                return False
            else:
                self.state = AgentState.IDLE
                return True
        
        else: 
            return True

    async def on_vad_interrupt(self, session):
        
        if self.state != AgentState.SPEAKING:
            return
            
        self.pending_interrupt = asyncio.get_event_loop().time() + self.pending_timeout
        
