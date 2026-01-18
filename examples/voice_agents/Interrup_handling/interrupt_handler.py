"""
Intelligent Interruption Filter for LiveKit Voice Agent

This module implements context-aware interruption filtering to distinguish between
passive acknowledgements (acknowledgment) and active interruptions based on agent state.
"""

import logging
import re
from typing import Set
from config import (
    DEFAULT_ACKNOWLEDGMENT_WORDS,
    DEFAULT_DIRECTIVE_WORDS,
)

logger = logging.getLogger(__name__)


class InterruptionFilter:
    """
    Filters interruptions based on transcript content and agent speaking state.
    
    Prevents the agent from stopping mid-speech when the user provides passive
    feedback (acknowledgment words like "yeah", "ok", "hmm"), while still allowing
    legitimate interruptions.
    """
    
    def __init__(
        self,
        acknowledgment_words: Set[str] | None = None,
        directive_words: Set[str] | None = None,
        min_word_threshold: int = 5
    ):
        """
        Initialize the interruption filter.
        
        Args:
            acknowledgment_words: Custom set of acknowledgment words (overrides defaults)
            directive_words: Custom set of directive words (overrides defaults)
            min_word_threshold: If transcript has more than this many words and
                            isn't purely acknowledgment, allow interruption
        """
        self.acknowledgment_words = acknowledgment_words or DEFAULT_ACKNOWLEDGMENT_WORDS
        self.directive_words = directive_words or DEFAULT_DIRECTIVE_WORDS
        self.min_word_threshold = min_word_threshold

        logger.info(
            f"InterruptionFilter initialized with {len(self.acknowledgment_words)} "
            f"acknowledgment words and {len(self.directive_words)} directive words"
        )

    
    def should_interrupt(self, transcript: str, agent_is_speaking: bool) -> bool:
        """
        Determine if the user input should interrupt the agent.
        
        Args:
            transcript: The user's transcribed speech
            agent_is_speaking: True if agent is currently speaking, False otherwise
        
        Returns:
            True if the agent should be interrupted, False if input should be ignored
        """
        if not transcript or not transcript.strip():
            # Empty transcript - no interruption
            return False
        
        # Normalize the transcript
        normalized = self._normalize_text(transcript)
        
        # Extract words
        words = self._extract_words(normalized)
        
        if not words:
            return False
        
        # Check for explicit directive words (always interrupt)
        if self._contains_directive(normalized, words):
            logger.debug(
                f"Interruption ALLOWED: directive word detected - "
                f"transcript='{transcript}', agent_speaking={agent_is_speaking}"
            )
            return True
        
        # If agent is not speaking, always process the input
        if not agent_is_speaking:
            logger.debug(
                f"Interruption ALLOWED: agent not speaking - transcript='{transcript}'"
            )
            return True
        
        # Agent IS speaking - check if this is pure acknowledgment
        if self._is_pure_acknowledgment(words):
            logger.info(
                f"Interruption BLOCKED: pure acknowledgment detected - "
                f"transcript='{transcript}', agent_speaking={agent_is_speaking}"
            )
            return False
        
        # Mixed or substantial input while agent is speaking - allow interruption
        logger.debug(
            f"Interruption ALLOWED: substantial input - "
            f"transcript='{transcript}', agent_speaking={agent_is_speaking}"
        )
        return True
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text by lowercasing and removing extra whitespace."""
        return " ".join(text.lower().strip().split())
    
    def _extract_words(self, text: str) -> list[str]:
        """
        Extract words from text, removing punctuation.
        
        Returns a list of cleaned words.
        """
        # Remove punctuation but keep hyphens in compound words
        text = re.sub(r'[^\w\s-]', ' ', text)
        # Split and filter empty strings
        words = [w.strip() for w in text.split() if w.strip()]
        return words
    
    def _contains_directive(self, normalized_text: str, words: list[str]) -> bool:
        """
        Check if the text contains any directive words.
        
        Checks both individual words and multi-word phrases.
        """
        # Check multi-word directive phrases first
        for directive in self.directive_words:
            if ' ' in directive and directive in normalized_text:
                return True
        
        # Check individual directive words
        for word in words:
            if word in self.directive_words:
                return True
        
        return False
    
    def _is_pure_acknowledgment(self, words: list[str]) -> bool:
        """
        Check if all words in the list are acknowledgment words.
        
        Args:
            words: List of cleaned words from user input
        
        Returns:
            True if ALL words are acknowledgment, False otherwise
        """
        if not words:
            return False
        
        # If there are too many words, it's probably not pure acknowledgment
        if len(words) > self.min_word_threshold:
            return False
        
        # Check if all words are in the acknowledgment set
        for word in words:
            # First check if the whole word (including hyphens) is in the set
            if word in self.acknowledgment_words:
                continue
            # If not, try splitting hyphenated words and check each part
            elif '-' in word:
                parts = word.split('-')
                if not all(part in self.acknowledgment_words for part in parts if part):
                    return False
            else:
                # Word is not acknowledgment
                return False
        return True
    
    def is_acknowledgment_word(self, word: str) -> bool:
        """Check if a single word is a acknowledgment word."""
        normalized = word.lower().strip()
        # First check if the whole word is in the set
        if normalized in self.acknowledgment_words:
            return True
        # If not, try splitting hyphenated words
        if '-' in normalized:
            parts = normalized.split('-')
            return all(part in self.acknowledgment_words for part in parts if part)
        return False
    
    def add_acknowledgment_word(self, word: str) -> None:
        """Add a custom acknowledgment word to the filter."""
        self.acknowledgment_words.add(word.lower().strip())
        logger.debug(f"Added acknowledgment word: '{word}'")
    
    def add_directive_word(self, word: str) -> None:
        """Add a custom directive word to the filter."""
        self.directive_words.add(word.lower().strip())
        logger.debug(f"Added directive word: '{word}'")
    
    def remove_acknowledgment_word(self, word: str) -> None:
        """Remove a acknowledgment word from the filter."""
        self.acknowledgment_words.discard(word.lower().strip())
        logger.debug(f"Removed acknowledgment word: '{word}'")
    
    def remove_directive_word(self, word: str) -> None:
        """Remove a directive word from the filter."""
        self.directive_words.discard(word.lower().strip())
        logger.debug(f"Removed directive word: '{word}'")