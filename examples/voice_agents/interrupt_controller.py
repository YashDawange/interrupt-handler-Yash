import re
import os
import asyncio
from enum import Enum
from typing import Optional
from livekit.agents import AgentSession

class AgentState(Enum):
    SPEAKING = "speaking"
    WAITING = "waiting"
    IDLE = "idle"

class InterruptController:
    def __init__(self):
        self.state = AgentState.IDLE
        self.soft_tokens = set(os.getenv("SOFT_TOKENS", "yeah,ok,hmm,uh-huh,right,mm-hmm,aha").lower().split(","))
        self.hard_tokens = set(os.getenv("HARD_TOKENS", "stop,wait,no,hold,pause").lower().split(","))
        self.max_soft_length = int(os.getenv("MAX_SOFT_LENGTH", "3"))

    def normalize(self, text: str) -> list[str]:
        """Fast normalization"""
        text = re.sub(r'[^\w\s]', '', text.lower())
        words = text.split()
        ngrams = words.copy()
        for i in range(len(words)-1):
            ngrams.append(f"{words[i]} {words[i+1]}")
        return ngrams

    def classify(self, text: str) -> str:
        """Returns: SOFT_ONLY, HARD, NORMAL"""
        tokens = self.normalize(text)
        word_count = len([t for t in tokens if ' ' not in t])  # Count words only
        
        has_hard = any(t in self.hard_tokens for t in tokens)
        has_soft = any(t in self.soft_tokens for t in tokens)
        
        if has_hard:
            return "HARD"
        elif has_soft and word_count <= self.max_soft_length:
            return "SOFT_ONLY"
        else:
            return "NORMAL"

    def on_agent_started_speaking(self):
        """Agent starts speaking"""
        self.state = AgentState.SPEAKING

    def on_agent_stopped_speaking(self):
        """Agent finished speaking"""
        self.state = AgentState.WAITING

    def should_interrupt(self, user_text: str) -> tuple[bool, Optional[str]]:
        """
        Returns: (should_interrupt, response_override)
        - (False, None) = ignore completely
        - (True, None) = process normally
        - (False, "text") = respond with override message
        """
        classification = self.classify(user_text)
        
        if self.state == AgentState.SPEAKING:
            if classification == "SOFT_ONLY":
                # CRITICAL: Don't interrupt
                return (False, None)
            else:
                # Hard interrupt or normal speech
                return (True, None)
        
        elif self.state == AgentState.WAITING:
            if classification == "SOFT_ONLY":
                # Treat as affirmative answer
                return (False, "Great, let's continue.")
            else:
                return (True, None)
        
        else:  # IDLE
            return (True, None)
