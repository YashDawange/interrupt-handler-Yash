"""
Intelligent Interrupt Handler for LiveKit Agents
Handles context-aware interruptions based on agent speaking state
"""

import logging
import asyncio
from typing import Set, Optional
from dataclasses import dataclass

logger = logging.getLogger("interrupt-handler")


@dataclass
class InterruptConfig:
    """Configuration for interrupt handling"""
    ignore_words: Set[str]
    interrupt_words: Set[str]
    mixed_phrase_threshold: int = 2


class IntelligentInterruptHandler:
    """
    Handles intelligent interruption based on agent's speaking state.
    
    Behavior Matrix:
    1. Agent Speaking + Ignore Words → IGNORE (continue speaking)
    2. Agent Speaking + Interrupt Words → INTERRUPT
    3. Agent Silent + Ignore Words → RESPOND (treat as valid)
    4. Agent Silent + Interrupt Words → RESPOND
    """
    
    def __init__(self, config: Optional[InterruptConfig] = None):
        self.config = config or InterruptConfig(
            ignore_words={
                'yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'mhmm', 
                'right', 'aha', 'yep', 'yup', 'sure', 'alright',
                'uh', 'um', 'mm', 'mhm'
            },
            interrupt_words={
                'stop', 'wait', 'no', 'hold', 'pause', 'hang',
                'but', 'however', 'actually'
            }
        )
        
        self._is_agent_speaking = False
        self._last_decision = None
        
    def set_agent_speaking(self, is_speaking: bool):
        """Update the agent's speaking state"""
        self._is_agent_speaking = is_speaking
        logger.debug(f"Agent speaking state updated: {is_speaking}")
    
    def should_process_speech(self, transcription: str, is_final: bool = True) -> bool:
        """
        Determine if user speech should interrupt or be processed.
        
        Args:
            transcription: The transcribed text
            is_final: Whether this is a final transcription
            
        Returns:
            True if speech should be processed/interrupt
            False if speech should be ignored
        """
        if not is_final:
            # Don't make decisions on interim transcriptions
            return True
            
        text = transcription.lower().strip()
        
        if not text:
            return True
            
        # If agent is not speaking, process everything normally
        if not self._is_agent_speaking:
            logger.debug(f"Agent silent - processing input: '{text}'")
            self._last_decision = ("process", "agent_silent")
            return True
        
        # Agent IS speaking - apply intelligent filtering
        words = text.split()
        
        # Check for interrupt words (including in mixed phrases)
        has_interrupt_word = any(
            word in self.config.interrupt_words 
            for word in words
        )
        
        if has_interrupt_word:
            logger.info(f"✋ INTERRUPT detected while agent speaking: '{text}'")
            self._last_decision = ("interrupt", "has_interrupt_word")
            return True
        
        # Check if it's pure backchanneling
        is_pure_backchanneling = all(
            word in self.config.ignore_words or word == ''
            for word in words
        )
        
        if is_pure_backchanneling:
            logger.info(f"🔇 IGNORING backchanneling while agent speaking: '{text}'")
            self._last_decision = ("ignore", "pure_backchanneling")
            return False
        
        # Contains substantive words - might be a real question/statement
        logger.debug(f"⚠️ Processing potentially substantive speech: '{text}'")
        self._last_decision = ("process", "substantive_content")
        return True
    
    def get_last_decision(self) -> Optional[tuple]:
        """Get the last decision made (for debugging/testing)"""
        return self._last_decision


def create_interrupt_config_from_env() -> InterruptConfig:
    """Create interrupt config from environment variables"""
    import os
    
    ignore_list = os.getenv(
        'INTERRUPT_IGNORE_WORDS',
        'yeah,ok,okay,hmm,uh-huh,mhmm,right,aha,yep,yup,sure,alright,uh,um,mm,mhm'
    )
    
    interrupt_list = os.getenv(
        'INTERRUPT_WORDS',
        'stop,wait,no,hold,pause,hang,but,however,actually'
    )
    
    return InterruptConfig(
        ignore_words=set(word.strip().lower() for word in ignore_list.split(',') if word.strip()),
        interrupt_words=set(word.strip().lower() for word in interrupt_list.split(',') if word.strip())
    )
