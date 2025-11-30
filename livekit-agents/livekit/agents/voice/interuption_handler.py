from dataclasses import dataclass
from typing import Set
import os
import re


@dataclass
class InterruptionConfig:
    """Configuration for interruption handling"""
    ignore_words: Set[str]
    interrupt_words: Set[str]
    
    @staticmethod
    def from_env() -> 'InterruptionConfig':
        """Load configuration from environment variables"""
        ignore_words_str = os.getenv(
            'AGENT_IGNORE_WORDS', 
            'yeah,ok,hmm,right,uh-huh,mhm,aha,okay'
        )
        interrupt_words_str = os.getenv(
            'AGENT_INTERRUPT_WORDS',
            'wait,stop,no,hold on,pause,hold,hang on'
        )
        
        return InterruptionConfig(
            ignore_words=set(w.strip().lower() for w in ignore_words_str.split(',')),
            interrupt_words=set(w.strip().lower() for w in interrupt_words_str.split(','))
        )


class InterruptionHandler:
    def __init__(self, config: InterruptionConfig | None = None):
        self.config = config or InterruptionConfig.from_env()
        self._agent_speaking = False
        
    def set_agent_state(self, speaking: bool) -> None:
        """Update whether agent is currently speaking"""
        self._agent_speaking = speaking
        
    def should_interrupt(self, transcript: str) -> bool:
        """
        Determine if transcript should interrupt agent
        
        Args:
            transcript: The user's speech transcript to evaluate
            
        Returns:
            True if should interrupt/process, False if should ignore
        """
        if not self._agent_speaking:
            # Agent is silent - always process input
            return True
            
        # Agent is speaking - check if input should interrupt
        transcript_lower = transcript.lower().strip()
        
        # Split into words (simple whitespace split)
        words = set(transcript_lower.split())
        
        # Check for interrupt commands first (highest priority)
        if words & self.config.interrupt_words:
            return True
            
        # Check if it's ONLY ignore words (backchannel)
        if words and words.issubset(self.config.ignore_words):
            return False
            
        # Mixed input or other words - allow interruption
        return True