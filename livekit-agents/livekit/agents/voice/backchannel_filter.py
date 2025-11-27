"""
Backchannel Filter Module

This module provides intelligent filtering of user speech to distinguish between:
1. "Backchannel" words (yeah, ok, hmm, right, uh-huh) - passive acknowledgments
2. Real interruptions (wait, stop, no) - active commands

The filter is context-aware and only applies when the agent is actively speaking.
When the agent is silent, all user input is treated as valid conversational input.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Set, Optional


@dataclass
class BackchannelConfig:
    """Configuration for backchannel filtering."""
    
    # Default backchannel words that should be ignored when agent is speaking
    DEFAULT_BACKCHANNEL_WORDS = {
        # Affirmations
        'yeah', 'yep', 'yes', 'yup', 'ya', 'aye',
        # Acknowledgments  
        'ok', 'okay', 'k',
        # Thinking/filler sounds
        'hmm', 'hm', 'mhmm', 'mm', 'mmm', 'mm-hmm', 'mmhmm',
        'uh-huh', 'uhuh', 'huh',
        # Agreement words
        'right', 'alright', 'gotcha',
        # Casual acknowledgments
        'sure', 'cool', 'nice', 'great', 'good', 'fine',
        'true', 'correct', 'exactly', 'absolutely',
        'definitely', 'totally', 'certainly', 'indeed',
        # Filler sounds
        'ah', 'oh', 'uh', 'um', 'er',
        # Reactions
        'wow', 'really', 'seriously', 'interesting',
    }
    
    # Words that should always trigger an interruption
    INTERRUPT_WORDS = {
        'wait', 'stop', 'hold', 'pause', 'hang on',
        'no', 'nope', 'nah',
        'excuse me', 'sorry', 'pardon',
    }
    
    def __init__(
        self,
        ignore_words: Optional[Set[str]] = None,
        interrupt_words: Optional[Set[str]] = None,
        case_sensitive: bool = False,
    ):
        """
        Initialize backchannel filter configuration.
        
        Args:
            ignore_words: Set of words to ignore when agent is speaking.
                         If None, uses DEFAULT_BACKCHANNEL_WORDS.
            interrupt_words: Set of words that always trigger interruption.
                           If None, uses INTERRUPT_WORDS.
            case_sensitive: Whether word matching is case-sensitive.
        """
        self.ignore_words = ignore_words or self.DEFAULT_BACKCHANNEL_WORDS.copy()
        self.interrupt_words = interrupt_words or self.INTERRUPT_WORDS.copy()
        self.case_sensitive = case_sensitive
        
        # Load additional words from environment variable
        env_words = os.getenv('BACKCHANNEL_IGNORE_WORDS')
        if env_words:
            additional_words = {w.strip() for w in env_words.split(',')}
            self.ignore_words.update(additional_words)
    
    def add_ignore_word(self, word: str) -> None:
        """Add a word to the backchannel ignore list."""
        self.ignore_words.add(word.lower() if not self.case_sensitive else word)
    
    def add_interrupt_word(self, word: str) -> None:
        """Add a word to the interrupt trigger list."""
        self.interrupt_words.add(word.lower() if not self.case_sensitive else word)
    
    def remove_ignore_word(self, word: str) -> None:
        """Remove a word from the backchannel ignore list."""
        self.ignore_words.discard(word.lower() if not self.case_sensitive else word)


class BackchannelFilter:
    """
    Filter for distinguishing between backchannel acknowledgments and real interruptions.
    
    This filter implements context-aware speech filtering that only applies when the
    agent is actively speaking. It uses semantic analysis to detect mixed sentences
    that contain both backchannel words and real commands.
    """
    
    def __init__(self, config: Optional[BackchannelConfig] = None):
        """
        Initialize the backchannel filter.
        
        Args:
            config: Configuration for backchannel filtering.
                   If None, uses default configuration.
        """
        self.config = config or BackchannelConfig()
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        text = text.strip()
        if not self.config.case_sensitive:
            text = text.lower()
        return text
    
    def _extract_words(self, text: str) -> Set[str]:
        """
        Extract words from text, handling multi-word phrases.
        
        Returns both individual words and common phrases.
        """
        normalized = self._normalize_text(text)
        
        # Check for common multi-word phrases FIRST (before word extraction)
        # This handles phrases that might be split by regex
        phrases = set()
        multi_word_phrases = [
            # Filler sounds with variations
            'uh-huh', 'uhuh', 'uh huh', 'mm-hmm', 'mmhmm', 'mm hmm',
            # Understanding phrases
            'got it', 'i see', 'i understand', 'makes sense',
            # Interrupt phrases (for detection)
            'hang on', 'hold on', 'excuse me', 'one moment', 'one second',
            # Agreement phrases
            'all right', 'of course', 'go on', 'go ahead', 'no way',
        ]
        for phrase in multi_word_phrases:
            if phrase in normalized:
                phrases.add(phrase)
        
        # Extract individual words (alphanumeric and hyphens)
        # Use \w which includes letters, numbers, and underscore
        words = set(re.findall(r'\b[\w-]+\b', normalized))
        
        return words | phrases
    
    def contains_interrupt_word(self, text: str) -> bool:
        """
        Check if text contains any interrupt trigger words.
        
        Args:
            text: The transcribed text to check.
            
        Returns:
            True if text contains interrupt words, False otherwise.
        """
        words = self._extract_words(text)
        return bool(words & self.config.interrupt_words)
    
    def is_backchannel_only(self, text: str) -> bool:
        """
        Check if text contains ONLY backchannel words.
        
        Args:
            text: The transcribed text to check.
            
        Returns:
            True if text contains only backchannel words, False if it contains
            any meaningful content or interrupt words.
        """
        if not text or not text.strip():
            return False
        
        # First check if it contains interrupt words
        if self.contains_interrupt_word(text):
            return False
        
        words = self._extract_words(text)
        
        # If no words extracted, not backchannel
        if not words:
            return False
        
        # Check if ALL words are in the ignore list
        return words.issubset(self.config.ignore_words)
    
    def should_ignore_input(self, text: str, agent_is_speaking: bool) -> bool:
        """
        Determine if user input should be ignored based on context.
        
        This is the main filtering function that implements the state-aware logic:
        - If agent is speaking AND text is backchannel-only → IGNORE
        - If agent is speaking AND text contains real commands → DON'T IGNORE (interrupt)
        - If agent is NOT speaking → NEVER IGNORE (treat as valid input)
        
        Args:
            text: The transcribed user input.
            agent_is_speaking: Whether the agent is currently generating/playing audio.
            
        Returns:
            True if the input should be ignored (filtered out), False otherwise.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # If agent is not speaking, never ignore input (state-aware behavior)
        if not agent_is_speaking:
            logger.info(f"[FILTER DEBUG] Agent NOT speaking → returning False (don't ignore)")
            return False
        
        # Agent is speaking - check if this is backchannel only
        is_backchannel = self.is_backchannel_only(text)
        logger.info(f"[FILTER DEBUG] Agent IS speaking, is_backchannel_only('{text}') = {is_backchannel}")
        return is_backchannel
    
    def classify_input(self, text: str, agent_is_speaking: bool) -> str:
        """
        Classify user input for debugging/logging purposes.
        
        Args:
            text: The transcribed user input.
            agent_is_speaking: Whether the agent is currently speaking.
            
        Returns:
            Classification string: 'IGNORE', 'INTERRUPT', or 'RESPOND'.
        """
        if not agent_is_speaking:
            return 'RESPOND'
        
        if self.contains_interrupt_word(text):
            return 'INTERRUPT'
        
        if self.is_backchannel_only(text):
            return 'IGNORE'
        
        return 'INTERRUPT'


def create_default_filter() -> BackchannelFilter:
    """
    Create a backchannel filter with default configuration.
    
    This is a convenience function for quickly creating a filter with
    standard settings. The filter will automatically load additional
    ignore words from the BACKCHANNEL_IGNORE_WORDS environment variable.
    
    Returns:
        BackchannelFilter instance with default configuration.
    """
    return BackchannelFilter(BackchannelConfig())
