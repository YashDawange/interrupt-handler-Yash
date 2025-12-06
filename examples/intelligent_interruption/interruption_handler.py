"""
Intelligent Interruption Handler

This module provides logic to distinguish between backchanneling (passive acknowledgements)
and active interruptions based on agent speaking state and transcript content.
"""

import os
import re
from typing import Set


class IntelligentInterruptionHandler:
    """
    Handles intelligent interruption filtering based on agent state and transcript content.
    
    When the agent is speaking:
    - Backchanneling words (yeah, ok, hmm) are ignored
    - Interruption commands (stop, wait, no) are processed
    - Mixed inputs containing commands are processed
    
    When the agent is silent:
    - All input is processed normally
    """

    def __init__(
        self,
        ignore_words: list[str] | None = None,
        command_words: list[str] | None = None,
    ):
        """
        Initialize the interruption handler.
        
        Args:
            ignore_words: List of backchanneling words to ignore when agent is speaking.
                         If None, loads from INTERRUPTION_IGNORE_WORDS env var.
            command_words: List of command words that should always interrupt.
                          If None, loads from INTERRUPTION_COMMAND_WORDS env var.
        """
        # Load ignore words from env or use defaults
        if ignore_words is None:
            ignore_str = os.getenv(
                "INTERRUPTION_IGNORE_WORDS",
                "yeah,ok,hmm,right,uh-huh,uh huh,yep,yeah yeah,okay,uh,um,mm-hmm,mm hmm"
            )
            ignore_words = [w.strip().lower() for w in ignore_str.split(",") if w.strip()]

        # Load command words from env or use defaults
        if command_words is None:
            command_str = os.getenv(
                "INTERRUPTION_COMMAND_WORDS",
                "stop,wait,no,hold on,hold,stop it,wait a second,wait a minute"
            )
            command_words = [w.strip().lower() for w in command_str.split(",") if w.strip()]

        # Convert to sets for O(1) lookup
        self._ignore_words: Set[str] = {w.lower() for w in ignore_words}
        self._command_words: Set[str] = {w.lower() for w in command_words}
        
        # Track agent speaking state
        self._agent_is_speaking: bool = False

    def set_agent_speaking(self, is_speaking: bool) -> None:
        """Update the agent speaking state."""
        self._agent_is_speaking = is_speaking

    def should_ignore_interruption(self, transcript: str) -> bool:
        """
        Determine if an interruption should be ignored based on transcript and agent state.
        
        Args:
            transcript: The user's transcribed input (interim or final)
            
        Returns:
            True if the interruption should be ignored (agent continues speaking)
            False if the interruption should be processed (agent stops)
        """
        # If agent is not speaking, never ignore - process all input normally
        if not self._agent_is_speaking:
            return False

        # Normalize transcript
        normalized = self._normalize_transcript(transcript)
        
        # If transcript is empty after normalization, ignore
        if not normalized:
            return True

        # Check for command words first (these should always interrupt)
        if self._contains_command_word(normalized):
            return False  # Don't ignore - this is a real interruption

        # Check if all words are in the ignore list
        words = self._extract_words(normalized)
        if not words:
            return True  # No words found, ignore

        # If all words are backchanneling words, ignore the interruption
        all_ignored = all(word in self._ignore_words for word in words)
        return all_ignored

    def _normalize_transcript(self, transcript: str) -> str:
        """Normalize transcript to lowercase and clean up."""
        if not transcript:
            return ""
        # Convert to lowercase and strip
        normalized = transcript.lower().strip()
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def _extract_words(self, text: str) -> list[str]:
        """Extract individual words from text."""
        if not text:
            return []
        # Split on whitespace and punctuation, but keep hyphenated words together
        words = re.findall(r'\b[\w-]+\b', text.lower())
        return words

    def _contains_command_word(self, text: str) -> bool:
        """
        Check if text contains any command word.
        
        This handles both single words and phrases (e.g., "hold on").
        """
        text_lower = text.lower()
        
        # Check for phrase matches first (longer phrases first)
        sorted_commands = sorted(self._command_words, key=len, reverse=True)
        for command in sorted_commands:
            if command in text_lower:
                return True
        
        return False

    def get_ignore_words(self) -> Set[str]:
        """Get the current set of ignore words."""
        return self._ignore_words.copy()

    def get_command_words(self) -> Set[str]:
        """Get the current set of command words."""
        return self._command_words.copy()

