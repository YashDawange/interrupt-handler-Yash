import logging
import os
import re
from typing import Set, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("interruption-engine")


class InterruptionDecision(Enum):
    """Enumeration of possible interruption decisions."""
    ALLOW_NORMAL = "allow_normal"
    IGNORE_BACKCHANNEL = "ignore_backchannel"
    FORCE_INTERRUPT = "force_interrupt"


@dataclass
class TranscriptAnalysis:
    """Data class to hold analysis results of user transcript."""
    text: str
    tokens: List[str]
    is_pure_acknowledgment: bool
    has_interrupt_signal: bool
    decision: InterruptionDecision
    confidence: float


class VocabularyManager:
    """
    Manages word vocabularies for acknowledgment detection and interruption signals.
    Supports environment-based configuration for flexible deployment.
    """
    
    # Core acknowledgment vocabulary - these are conversational fillers
    BASE_ACKNOWLEDGMENTS = {
        "ah", "aha", "hm", "hmm", "mhm", "mhmm", "mm-hmm", "mmhmm", 
        "uh-huh", "um", "uh", "uhhuh", "absolutely", "exactly", "indeed", 
        "right", "sure", "true", "understood", "correct", "definitely",
        "alright", "cool", "fine", "nice", "ok", "okay", "yeah", "yep", 
        "yes", "yup", "sounds good", "go on", "got it", "i see", 
        "makes sense", "keep going", "tell me more", "really", "wow", 
        "for real", "seriously", "interesting", "no way",
    }
    
    # Explicit interruption signals - these demand attention
    BASE_INTERRUPTIONS = {
        "stop", "wait", "no", "hold", "cancel", "pause", 
        "enough", "hold on",
    }
    
    def __init__(self):
        """Initialize vocabularies from environment or use defaults."""
        self.acknowledgments = self._load_vocabulary(
            "BACKCHANNEL_WORDS", 
            self.BASE_ACKNOWLEDGMENTS
        )
        self.interruptions = self._load_vocabulary(
            "INTERRUPT_WORDS", 
            self.BASE_INTERRUPTIONS
        )
        logger.info(
            f"Vocabulary loaded: {len(self.acknowledgments)} acknowledgments, "
            f"{len(self.interruptions)} interruption signals"
        )
    
    def _load_vocabulary(self, env_key: str, default_set: Set[str]) -> Set[str]:
        """Load vocabulary from environment variable or return default."""
        env_value = os.getenv(env_key)
        if not env_value:
            return default_set
        
        custom_words = {
            word.strip().lower() 
            for word in env_value.split(",") 
            if word.strip()
        }
        logger.debug(f"Loaded custom vocabulary from {env_key}: {len(custom_words)} words")
        return custom_words
    
    def is_acknowledgment(self, token: str) -> bool:
        """Check if a token is an acknowledgment word."""
        return token.lower() in self.acknowledgments
    
    def is_interruption_signal(self, token: str) -> bool:
        """Check if a token is an explicit interruption signal."""
        return token.lower() in self.interruptions


class TextProcessor:
    """
    Handles text normalization and tokenization for consistent analysis.
    Provides utilities for processing user speech transcripts.
    """
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Extract meaningful tokens from text by removing punctuation.
        Converts to lowercase for case-insensitive matching.
        """
        tokens = [
            token for token in re.split(r"\W+", text.lower()) 
            if token
        ]
        return tokens
    
    @staticmethod
    def normalize(text: str) -> str:
        """Normalize text by stripping whitespace and lowercasing."""
        return text.strip().lower()
    
    @staticmethod
    def is_empty(text: str) -> bool:
        """Check if text is empty or contains only whitespace."""
        return not text or not text.strip()


class InterruptionEngine:
    """
    Core engine that analyzes user speech and decides whether to interrupt the agent.
    Implements sophisticated logic to differentiate between acknowledgments and real interrupts.
    
    Design Philosophy:
    - Acknowledge user engagement without disrupting agent flow
    - Respond immediately to explicit interruption signals
    - Handle mixed utterances intelligently
    """
    
    def __init__(self, vocabulary_manager: VocabularyManager):
        """Initialize engine with vocabulary manager for word classification."""
        self.vocab = vocabulary_manager
        self.text_processor = TextProcessor()
        self._agent_speaking_state = False
        logger.info("Interruption engine initialized and ready")
    
    def set_agent_state(self, is_speaking: bool):
        """Update the current speaking state of the agent."""
        state_change = "started" if is_speaking and not self._agent_speaking_state else "stopped"
        if is_speaking != self._agent_speaking_state:
            logger.debug(f"Agent {state_change} speaking")
        self._agent_speaking_state = is_speaking
    
    def is_agent_speaking(self) -> bool:
        """Query current agent speaking state."""
        return self._agent_speaking_state
    
    def analyze_transcript(self, text: str, is_final: bool) -> TranscriptAnalysis:
        """
        Perform comprehensive analysis of user transcript.
        Returns detailed analysis including interruption decision.
        """
        # Extract tokens for analysis
        tokens = self.text_processor.tokenize(text)
        
        # Classify the utterance
        is_pure_ack = self._is_pure_acknowledgment(tokens)
        has_interrupt = self._contains_interruption_signal(tokens)
        
        # Determine appropriate action based on context
        decision = self._make_decision(
            tokens=tokens,
            is_pure_ack=is_pure_ack,
            has_interrupt=has_interrupt,
            is_final=is_final
        )
        
        # Calculate confidence score (simple heuristic)
        confidence = self._calculate_confidence(tokens, is_pure_ack, has_interrupt)
        
        return TranscriptAnalysis(
            text=text,
            tokens=tokens,
            is_pure_acknowledgment=is_pure_ack,
            has_interrupt_signal=has_interrupt,
            decision=decision,
            confidence=confidence
        )
    
    def _is_pure_acknowledgment(self, tokens: List[str]) -> bool:
        """
        Determine if ALL tokens are acknowledgment words.
        Pure acknowledgments should not interrupt the agent.
        """
        if not tokens:
            return False
        return all(self.vocab.is_acknowledgment(tok) for tok in tokens)
    
    def _contains_interruption_signal(self, tokens: List[str]) -> bool:
        """
        Check if ANY token is an explicit interruption signal.
        These always trigger an interrupt.
        """
        return any(self.vocab.is_interruption_signal(tok) for tok in tokens)
    
    def _make_decision(
        self, 
        tokens: List[str], 
        is_pure_ack: bool, 
        has_interrupt: bool,
        is_final: bool
    ) -> InterruptionDecision:
        """
        Core decision logic that determines how to handle the user's speech.
        
        Decision Tree:
        1. Agent not speaking → Allow normal processing
        2. Interim transcript → Allow normal processing (wait for final)
        3. Pure acknowledgment while speaking → Ignore (don't interrupt)
        4. Contains interrupt signal → Force interrupt
        5. Mixed content while speaking → Force interrupt
        """
        
        # Rule 1: If agent isn't speaking, process normally
        if not self._agent_speaking_state:
            logger.debug("Decision: ALLOW_NORMAL (agent idle)")
            return InterruptionDecision.ALLOW_NORMAL
        
        # Rule 2: Only process final transcripts to avoid false positives
        if not is_final:
            logger.debug("Decision: ALLOW_NORMAL (interim transcript)")
            return InterruptionDecision.ALLOW_NORMAL
        
        # Rule 3: Pure acknowledgments should be filtered out
        if is_pure_ack:
            logger.info(f"Decision: IGNORE_BACKCHANNEL - Pure acknowledgment detected")
            return InterruptionDecision.IGNORE_BACKCHANNEL
        
        # Rule 4: Explicit interruption signals always interrupt
        if has_interrupt:
            logger.info(f"Decision: FORCE_INTERRUPT - Interruption signal detected")
            return InterruptionDecision.FORCE_INTERRUPT
        
        # Rule 5: Any other content while agent is speaking is treated as interrupt
        logger.info(f"Decision: FORCE_INTERRUPT - Non-acknowledgment content during speech")
        return InterruptionDecision.FORCE_INTERRUPT
    
    def _calculate_confidence(
        self, 
        tokens: List[str], 
        is_pure_ack: bool, 
        has_interrupt: bool
    ) -> float:
        """
        Calculate confidence score for the decision (0.0 to 1.0).
        Higher confidence for clear-cut cases.
        """
        if not tokens:
            return 0.0
        
        if has_interrupt:
            return 1.0  # Very confident about explicit interrupts
        
        if is_pure_ack:
            return 0.95  # Very confident about pure acknowledgments
        
        # Mixed content - moderate confidence
        ack_ratio = sum(1 for t in tokens if self.vocab.is_acknowledgment(t)) / len(tokens)
        return 0.7 + (0.3 * (1 - ack_ratio))  # Higher confidence if fewer acknowledgments


class SmartInterruptionHandler:
    """
    High-level handler that coordinates the interruption engine.
    Provides simple interface for the agent session to use.
    """
    
    def __init__(self):
        """Initialize handler with all necessary components."""
        self.vocab_manager = VocabularyManager()
        self.engine = InterruptionEngine(self.vocab_manager)
        self.text_processor = TextProcessor()
        logger.info("Smart interruption handler ready")
    
    def update_agent_speaking_state(self, is_speaking: bool):
        """Forward agent state updates to the engine."""
        self.engine.set_agent_state(is_speaking)
    
    def should_interrupt(self, text: str, is_final: bool) -> Tuple[bool, str]:
        """
        Main entry point: analyze text and return interruption decision.
        
        Returns:
            Tuple[bool, str]: (should_interrupt, reason_code)
        """
        # Handle empty input
        if self.text_processor.is_empty(text):
            return (False, "empty_input")
        
        # Perform analysis
        analysis = self.engine.analyze_transcript(text, is_final)
        
        # Map decision to boolean and reason
        if analysis.decision == InterruptionDecision.IGNORE_BACKCHANNEL:
            return (False, "soft_backchannel")
        elif analysis.decision == InterruptionDecision.FORCE_INTERRUPT:
            reason = "strong_interrupt" if analysis.has_interrupt_signal else "mixed_input"
            return (True, reason)
        else:
            return (False, "agent_not_speaking" if not self.engine.is_agent_speaking() else "interim_transcript")
    
    # Convenience methods for backward compatibility
    def is_soft_backchannel(self, text: str) -> bool:
        """Check if text is a pure acknowledgment."""
        tokens = self.text_processor.tokenize(text)
        return self.engine._is_pure_acknowledgment(tokens)
    
    def contains_strong_interrupt(self, text: str) -> bool:
        """Check if text contains interruption signals."""
        tokens = self.text_processor.tokenize(text)
        return self.engine._contains_interruption_signal(tokens)