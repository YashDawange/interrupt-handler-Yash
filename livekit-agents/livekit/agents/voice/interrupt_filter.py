"""
Intelligent interruption filtering logic.

This module provides semantic analysis to determine whether user input
should interrupt the agent or be ignored based on context and content.
"""

import logging
import sys
from typing import Set

from .interrupt_config import BACKCHANNEL_WORDS, INTERRUPTION_COMMANDS

logger = logging.getLogger(__name__)

def debug_print(msg: str) -> None:
    """Print debug message that ALWAYS shows in console."""
    sys.stderr.write(f"\n {msg}\n")
    sys.stderr.flush()


class InterruptionFilter:
    """
    Filters user transcripts to distinguish between backchanneling
    (passive acknowledgments) and real interruptions.
    
    The filter is context-aware and considers whether the agent is
    currently speaking when making decisions.
    """
    
    def __init__(
        self,
        backchannel_words: Set[str] | None = None,
        interruption_commands: Set[str] | None = None,
    ):
        """
        Initialize the interruption filter.
        
        Args:
            backchannel_words: Set of words to ignore when agent is speaking.
                              If None, uses default from config.
            interruption_commands: Set of words that always interrupt.
                                  If None, uses default from config.
        """
        self.backchannel_words = backchannel_words or BACKCHANNEL_WORDS
        self.interruption_commands = interruption_commands or INTERRUPTION_COMMANDS
        
        logger.info(
            f"InterruptionFilter initialized with {len(self.backchannel_words)} "
            f"backchannel words and {len(self.interruption_commands)} interruption commands"
        )
    
    def should_ignore_transcript(
        self,
        transcript: str,
        agent_is_speaking: bool,
    ) -> bool:
        """
        Determine if a transcript should be ignored (not cause interruption).
        
        Logic matrix:
        - Agent speaking + backchannel word only → IGNORE (True)
        - Agent speaking + interruption command → INTERRUPT (False)
        - Agent speaking + mixed input → INTERRUPT (False)
        - Agent silent + any input → PROCESS (False)
        
        Args:
            transcript: The user's speech transcript
            agent_is_speaking: Whether the agent is currently speaking
            
        Returns:
            True if the transcript should be ignored (don't interrupt)
            False if it should cause an interruption or be processed normally
        """
        
        debug_print(f"FILTER CALLED: agent_speaking={agent_is_speaking}, text='{transcript}'")
        
        if not transcript or not transcript.strip():
            return True  # Empty transcript, ignore
        
        # If agent is not speaking, never ignore - process all input normally
        if not agent_is_speaking:
            debug_print(f"Agent NOT speaking - processing normally: '{transcript}'")
            return False
        
        # Agent IS speaking - check if this is just backchannel 
        debug_print(f"Agent IS speaking - checking backchannel: '{transcript}'")
        normalized_transcript = transcript.lower().strip()
        words = normalized_transcript.split()
        debug_print(f"Words: {words}")
        
        # Check for interruption commands (high priority)
        if self._contains_interruption_command(words):
            debug_print(f"INTERRUPT COMMAND detected: '{transcript}' -> ALLOWING interrupt")
            return False  # Don't ignore, allow interruption
        
        # Check if ALL words are backchannel words
        if self._is_pure_backchannel(words):
            debug_print(f"BACKCHANNEL detected: '{transcript}' -> IGNORING")
            return True  # Ignore - it's just passive feedback
        
        # Mixed input or unknown words - treat as interruption
        debug_print(f"MIXED/UNKNOWN input: '{transcript}' -> ALLOWING interrupt")
        return False
    
    def _contains_interruption_command(self, words: list[str]) -> bool:
        """
        Check if any word in the list is an interruption command.
        
        Args:
            words: List of words from transcript (already lowercase)
            
        Returns:
            True if any interruption command is found
        """
        for word in words:
            if word in self.interruption_commands:
                return True
        return False
    
    def _is_pure_backchannel(self, words: list[str]) -> bool:
        """
        Check if ALL words are backchannel words.
        
        This ensures that mixed inputs like "yeah but wait" are not
        considered pure backchannel.
        
        Args:
            words: List of words from transcript (already lowercase)
            
        Returns:
            True if all words are backchannel words
        """
        if not words:
            return False
        
        # Check each word
        for word in words:
            if word not in self.backchannel_words:
                return False
        
        return True
    
    def get_filter_reason(
        self,
        transcript: str,
        agent_is_speaking: bool,
    ) -> str:
        """
        Get a human-readable explanation for filter decision.
        
        Useful for debugging and logging.
        
        Args:
            transcript: The user's speech transcript
            agent_is_speaking: Whether the agent is currently speaking
            
        Returns:
            String explaining the filter decision
        """
        if not transcript or not transcript.strip():
            return "Empty transcript"
        
        if not agent_is_speaking:
            return "Agent not speaking - process normally"
        
        normalized_transcript = transcript.lower().strip()
        words = normalized_transcript.split()
        
        if self._contains_interruption_command(words):
            return f"Contains interruption command: {transcript}"
        
        if self._is_pure_backchannel(words):
            return f"Pure backchannel feedback: {transcript}"
        
        return f"Mixed/unknown input: {transcript}"
