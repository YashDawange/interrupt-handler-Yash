import logging
from typing import Set, Optional
import re

logger = logging.getLogger("interrupt-handler")

class IntelligentInterruptionHandler:
    """
    Handles context-aware interruptions for LiveKit voice agents.
    
    Key Features:
    - Ignores backchannel signals ("yeah", "ok", "hmm") when agent is speaking
    - Allows real interruptions ("stop", "wait", "no")
    - Responds to backchannel when agent is silent
    """
    
    # Configurable ignore list (backchannel signals)
    DEFAULT_BACKCHANNEL_WORDS: Set[str] = {
        "yeah", "ok", "okay", "hmm", "uh-huh", "right", 
        "mhm", "aha", "yep", "sure", "gotcha", "huh",
        "mm-hmm", "uh huh", "mm", "mhmm", "yup", "uh"
    }
    
    # Words that should always interrupt (even while speaking)
    INTERRUPT_WORDS: Set[str] = {
        "stop", "wait", "no", "hold", "pause", "hang on",
        "hold on", "hang", "interrupt", "but", "however",
        "actually", "listen"
    }
    
    def __init__(self, backchannel_words: Optional[Set[str]] = None):
        """
        Initialize the handler.
        
        Args:
            backchannel_words: Custom set of words to treat as backchannel.
                              If None, uses DEFAULT_BACKCHANNEL_WORDS.
        """
        self.backchannel_words = backchannel_words or self.DEFAULT_BACKCHANNEL_WORDS
        self.agent_is_speaking = False
        
        logger.info(f"✅ Initialized IntelligentInterruptionHandler")
        logger.info(f"   Backchannel words: {self.backchannel_words}")
        logger.info(f"   Interrupt words: {self.INTERRUPT_WORDS}")
    
    def set_agent_speaking_state(self, is_speaking: bool):
        """
        Update the agent's speaking state.
        
        Args:
            is_speaking: True if agent is currently generating/playing audio
        """
        old_state = self.agent_is_speaking
        self.agent_is_speaking = is_speaking
        
        if old_state != is_speaking:
            logger.debug(f"🔄 Agent state changed: {'SILENT' if old_state else 'SPEAKING'} → {'SPEAKING' if is_speaking else 'SILENT'}")
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (lowercase, no punctuation)"""
        text = re.sub(r'[^\w\s-]', '', text.lower())
        text = ' '.join(text.split())
        return text
    
    def _contains_interrupt_word(self, text: str) -> bool:
        """Check if text contains any interrupt words"""
        normalized = self._normalize_text(text)
        words = normalized.split()
        
        # Check for exact word matches and phrases
        for interrupt_word in self.INTERRUPT_WORDS:
            normalized_interrupt = self._normalize_text(interrupt_word)
            
            # Check both as individual word and as part of phrase
            if normalized_interrupt in words:
                return True
            
            # For multi-word phrases like "hang on"
            if ' ' in normalized_interrupt and normalized_interrupt in normalized:
                return True
        
        return False
    
    def _is_only_backchannel(self, text: str) -> bool:
        """Check if text contains only backchannel words (no other content)"""
        normalized = self._normalize_text(text)
        
        if not normalized:
            return True  # Empty is considered backchannel
        
        words = normalized.split()
        
        # Check if ALL words are backchannel
        for word in words:
            # Check exact matches first
            if word in [self._normalize_text(bc) for bc in self.backchannel_words]:
                continue
            
            # Check if word is part of multi-word backchannel (e.g., "uh" in "uh-huh")
            is_bc_part = False
            for bc_word in self.backchannel_words:
                normalized_bc = self._normalize_text(bc_word)
                if word in normalized_bc.replace('-', ' ').split():
                    is_bc_part = True
                    break
            
            if not is_bc_part:
                return False  # Found a non-backchannel word
        
        return True
    
    def should_interrupt(self, transcription: str) -> bool:
        """
        Determine if the user's input should interrupt the agent.
        
        Logic Matrix:
        1. Contains interrupt word (stop/wait/no) → ALWAYS INTERRUPT
        2. Agent SPEAKING + only backchannel → IGNORE (don't interrupt)
        3. Agent SILENT + any input → RESPOND (allow through)
        4. Agent SPEAKING + non-backchannel → INTERRUPT
        
        Args:
            transcription: The transcribed user speech
            
        Returns:
            True if agent should be interrupted, False otherwise
        """
        if not transcription or not transcription.strip():
            logger.debug("⚠️  Empty transcription, allowing through")
            return True
        
        text = transcription.strip()
        
        logger.info(f"")
        logger.info(f"{'='*70}")
        logger.info(f"📝 [TRANSCRIPTION] '{text}'")
        logger.info(f"🤖 [AGENT STATE] {'🗣️  SPEAKING' if self.agent_is_speaking else '🤐 SILENT'}")
        
        # PRIORITY 1: Check for interrupt words (highest priority)
        if self._contains_interrupt_word(text):
            logger.info(f"  ├─ ⚠️  Contains interrupt word → INTERRUPT")
            logger.info(f"  └─ ✅ Decision: INTERRUPT")
            logger.info(f"{'='*70}")
            return True
        
        # PRIORITY 2: Check if it's only backchannel
        is_backchannel_only = self._is_only_backchannel(text)
        logger.info(f"  ├─ Backchannel only: {is_backchannel_only}")
        
        # If agent is SPEAKING and it's ONLY backchannel → IGNORE
        if self.agent_is_speaking and is_backchannel_only:
            logger.info(f"  ├─ 🚫 Agent speaking + backchannel → IGNORE")
            logger.info(f"  └─ 🛡️  Decision: DO NOT INTERRUPT")
            logger.info(f"{'='*70}")
            return False
        
        # If agent is SILENT → always respond
        if not self.agent_is_speaking:
            logger.info(f"  ├─ ✓ Agent silent → RESPOND")
            logger.info(f"  └─ ✅ Decision: ALLOW (process as input)")
            logger.info(f"{'='*70}")
            return True
        
        # Default: Agent speaking + non-backchannel content → INTERRUPT
        logger.info(f"  ├─ ⚠️  Agent speaking + real content → INTERRUPT")
        logger.info(f"  └─ ✅ Decision: INTERRUPT")
        logger.info(f"{'='*70}")
        return True
    
    def process_transcription(self, transcription: str, agent_speaking: bool) -> bool:
        """
        Convenience method that combines state update and decision.
        
        Args:
            transcription: The user's transcribed speech
            agent_speaking: Current agent speaking state
            
        Returns:
            True if should interrupt, False otherwise
        """
        self.set_agent_speaking_state(agent_speaking)
        return self.should_interrupt(transcription)
