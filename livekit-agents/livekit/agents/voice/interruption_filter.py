"""
Intelligent interruption filtering for LiveKit agents.

This module provides logic to distinguish between backchannel acknowledgments
(like "yeah", "ok", "hmm") and actual interruptions when the agent is speaking.
"""

from __future__ import annotations

import re
from typing import Set

# Default backchannel words that should be ignored when agent is speaking
DEFAULT_BACKCHANNEL_WORDS: Set[str] = {
    "yeah",
    "yes",
    "yep",
    "yup",
    "ok",
    "okay",
    "kay",
    "hmm",
    "hm",
    "mhm",
    "mm",
    "uh-huh",
    "uh huh",
    "uhuh",
    "right",
    "aha",
    "ah",
    "uh",
    "um",
    "sure",
    "got it",
    "i see",
}

# Command words that should always trigger interruption
DEFAULT_COMMAND_WORDS: Set[str] = {
    "stop",
    "wait",
    "hold on",
    "hold up",
    "pause",
    "no",
    "nope",
    "but",
    "however",
    "actually",
    "excuse me",
    "sorry",
    "pardon",
}


class InterruptionFilter:
    """
    Filters user input to determine if it should interrupt the agent's speech.
    
    When the agent is speaking:
    - Backchannel words (e.g., "yeah", "ok") are ignored
    - Command words (e.g., "stop", "wait") trigger interruption
    - Mixed input (backchannel + command) triggers interruption
    - Other input triggers interruption
    
    When the agent is silent:
    - All input is processed normally
    """
    
    def __init__(
        self,
        *,
        backchannel_words: Set[str] | None = None,
        command_words: Set[str] | None = None,
        enabled: bool = True,
    ):
        """
        Initialize the interruption filter.
        
        Args:
            backchannel_words: Set of words to ignore when agent is speaking.
                              If None, uses DEFAULT_BACKCHANNEL_WORDS.
            command_words: Set of words that always trigger interruption.
                          If None, uses DEFAULT_COMMAND_WORDS.
            enabled: Whether the filter is enabled. If False, all input triggers interruption.
        """
        self.backchannel_words = (
            backchannel_words if backchannel_words is not None 
            else DEFAULT_BACKCHANNEL_WORDS.copy()
        )
        self.command_words = (
            command_words if command_words is not None 
            else DEFAULT_COMMAND_WORDS.copy()
        )
        self.enabled = enabled
        
        # Normalize all words to lowercase for case-insensitive matching
        self.backchannel_words = {w.lower() for w in self.backchannel_words}
        self.command_words = {w.lower() for w in self.command_words}
    
    def should_interrupt(
        self,
        transcript: str,
        agent_is_speaking: bool,
    ) -> bool:
        """
        Determine if the given transcript should interrupt the agent.
        
        Args:
            transcript: The user's transcribed speech
            agent_is_speaking: Whether the agent is currently speaking
            
        Returns:
            True if the agent should be interrupted, False if input should be ignored
        """
        # If filter is disabled, always interrupt
        if not self.enabled:
            return True
        
        # If agent is not speaking, always process the input
        if not agent_is_speaking:
            return True
        
        # If transcript is empty, don't interrupt
        if not transcript or not transcript.strip():
            return False
        
        # Normalize transcript
        normalized_transcript = transcript.lower().strip()
        
        # Check if transcript contains any command words
        if self._contains_command_words(normalized_transcript):
            return True
        
        # Check if transcript contains ONLY backchannel words
        if self._is_only_backchannel(normalized_transcript):
            return False
        
        # If it's not backchannel-only and doesn't have commands, 
        # it's likely a real interruption
        return True
    
    def _contains_command_words(self, normalized_transcript: str) -> bool:
        """Check if transcript contains any command words."""
        # Split into words and check for exact matches
        words = self._extract_words(normalized_transcript)
        
        # Check for single-word commands
        if any(word in self.command_words for word in words):
            return True
        
        # Check for multi-word commands (e.g., "hold on", "hold up")
        for command in self.command_words:
            if ' ' in command and command in normalized_transcript:
                return True
        
        return False
    
    def _is_only_backchannel(self, normalized_transcript: str) -> bool:
        """Check if transcript contains only backchannel words."""
        words = self._extract_words(normalized_transcript)
        
        if not words:
            return False
        
        # Check if all words are backchannel words
        for word in words:
            # Check single-word backchannel
            if word in self.backchannel_words:
                continue
            
            # Check if it's part of a multi-word backchannel (e.g., "uh-huh")
            is_part_of_backchannel = False
            for backchannel in self.backchannel_words:
                if ' ' in backchannel or '-' in backchannel:
                    backchannel_words = re.split(r'[\s\-]+', backchannel)
                    if word in backchannel_words:
                        is_part_of_backchannel = True
                        break
            
            if not is_part_of_backchannel:
                return False
        
        # Also check for multi-word backchannel phrases
        for backchannel in self.backchannel_words:
            if (' ' in backchannel or '-' in backchannel) and backchannel in normalized_transcript:
                # If the entire transcript matches a multi-word backchannel, it's backchannel-only
                if normalized_transcript.replace('-', ' ') == backchannel.replace('-', ' '):
                    return True
        
        return True
    
    def _extract_words(self, text: str) -> list[str]:
        """Extract words from text, removing punctuation."""
        # Remove punctuation and split into words
        words = re.findall(r'\b\w+\b', text.lower())
        return words
    
    def add_backchannel_word(self, word: str) -> None:
        """Add a word to the backchannel list."""
        self.backchannel_words.add(word.lower())
    
    def add_command_word(self, word: str) -> None:
        """Add a word to the command list."""
        self.command_words.add(word.lower())
    
    def remove_backchannel_word(self, word: str) -> None:
        """Remove a word from the backchannel list."""
        self.backchannel_words.discard(word.lower())
    
    def remove_command_word(self, word: str) -> None:
        """Remove a word from the command list."""
        self.command_words.discard(word.lower())
