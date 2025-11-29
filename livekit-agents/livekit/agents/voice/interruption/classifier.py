"""Text classification for semantic interruption handling."""

from __future__ import annotations

import re
from enum import Enum

from .config import InterruptionConfig


class UtteranceType(Enum):
    """Classification of user utterance for interruption handling."""
    
    BACKCHANNEL = "backchannel"
    """Pure backchannel/filler speech (e.g., "yeah ok hmm")."""
    
    COMMAND = "command"
    """Explicit interruption command (e.g., "stop", "wait a second")."""
    
    NORMAL = "normal"
    """Normal content (questions, statements, corrections)."""


class InterruptionClassifier:
    """Classifies user utterances as backchannel, command, or normal content.
    
    This classifier uses rule-based matching to categorize text:
    1. Command phrases are checked first (substring match)
    2. Command tokens are checked next (word match)
    3. Pure backchannel is detected (all tokens in ignore list)
    4. Everything else is normal content
    
    The classifier is stateless and can be called on any text fragment.
    
    Example:
        >>> config = InterruptionConfig()
        >>> classifier = InterruptionClassifier(config)
        >>> 
        >>> classifier.classify("yeah ok")
        <UtteranceType.BACKCHANNEL: 'backchannel'>
        >>> 
        >>> classifier.classify("stop")
        <UtteranceType.COMMAND: 'command'>
        >>> 
        >>> classifier.classify("yeah wait a second")
        <UtteranceType.COMMAND: 'command'>
        >>> 
        >>> classifier.classify("What time is it?")
        <UtteranceType.NORMAL: 'normal'>
    """
    
    def __init__(self, config: InterruptionConfig):
        """Initialize classifier with configuration.
        
        Args:
            config: Interruption configuration containing word lists.
        """
        self.config = config
    
    def classify(self, text: str) -> UtteranceType:
        """Classify text as backchannel, command, or normal content.
        
        Algorithm:
        1. Normalize text (lowercase, strip whitespace)
        2. Check for command phrases (substring match)
        3. Check for command tokens (word match)
        4. Check if all tokens are backchannel
        5. Otherwise return normal
        
        Args:
            text: Raw STT text to classify.
        
        Returns:
            Classification of the utterance.
        
        Note:
            Empty text is classified as BACKCHANNEL (treated as noise).
        """
        # Normalize text
        normalized = text.lower().strip()
        
        # Empty text is treated as noise/backchannel
        if not normalized:
            return UtteranceType.BACKCHANNEL
        
        # Check command phrases first (they override backchannel)
        # These are substring matches, so "yeah wait a second" contains "wait a second"
        for phrase in self.config.command_phrases:
            if phrase in normalized:
                return UtteranceType.COMMAND
        
        # Tokenize: split on non-alphabetic characters
        # This handles punctuation, spaces, etc.
        tokens = [w for w in re.split(r'\W+', normalized) if w]
        
        if not tokens:
            # No meaningful tokens after splitting
            return UtteranceType.BACKCHANNEL
        
        # Check for command tokens
        # If ANY token is a command word, classify as command
        if any(token in self.config.command_words for token in tokens):
            return UtteranceType.COMMAND
        
        # Check if pure backchannel
        # ALL tokens must be in the ignore list
        if all(token in self.config.ignore_words for token in tokens):
            return UtteranceType.BACKCHANNEL
        
        # Everything else is normal content
        return UtteranceType.NORMAL
