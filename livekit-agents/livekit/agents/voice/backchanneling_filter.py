"""
Intelligent Backchanneling Filter for LiveKit Voice Agents

This module provides context-aware filtering to distinguish between:
- Passive acknowledgements ("yeah", "ok", "hmm") that should be IGNORED while agent speaks
- Active interruptions ("stop", "wait", "no") that should INTERRUPT the agent
- Valid input when agent is silent that should be processed normally

The filter prevents the agent from stopping on filler words while speaking,
solving the over-sensitive VAD problem.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Optional

logger = logging.getLogger("backchanneling-filter")


# Default filler words that should be IGNORED when agent is speaking
DEFAULT_FILLER_WORDS: FrozenSet[str] = frozenset({
    # English acknowledgements
    "yeah", "yea", "yes", "yep", "yup", "ya", "uh-huh", "uh huh", "uhuh",
    "mm-hmm", "mm hmm", "mmhmm", "mhm", "hmm", "hm", "mmm",
    "ok", "okay", "k", "alright", "right", "sure", "fine",
    "got it", "gotcha", "i see", "i understand",
    "aha", "ah", "oh", "ooh", "wow",
    # Short affirmations
    "good", "great", "nice", "cool", "awesome",
})

# Default command words that should ALWAYS interrupt (even in filler context)
DEFAULT_COMMAND_WORDS: FrozenSet[str] = frozenset({
    # Stop commands
    "stop", "wait", "hold", "pause", "halt", "enough", "quiet",
    # Negative/correction commands
    "no", "nope", "wrong", "incorrect", "actually", "but",
    # Attention commands  
    "hey", "listen", "excuse", "sorry", "help",
    # Question starters (indicate user wants to interject)
    "what", "why", "how", "when", "where", "who", "which",
    # Clarification
    "repeat", "again", "slower", "louder",
})


class BackchannelingResult(Enum):
    """Result of analyzing a transcript for backchanneling."""
    IGNORE = "ignore"      # Filler word while speaking - ignore completely
    INTERRUPT = "interrupt"  # Command word or mixed input - interrupt agent
    RESPOND = "respond"     # Agent is silent - process as normal input


@dataclass
class BackchannelingConfig:
    """Configuration for the backchanneling filter."""
    enabled: bool = True
    filler_words: FrozenSet[str] = field(default_factory=lambda: DEFAULT_FILLER_WORDS)
    command_words: FrozenSet[str] = field(default_factory=lambda: DEFAULT_COMMAND_WORDS)
    case_sensitive: bool = False
    
    @classmethod
    def from_env(cls) -> "BackchannelingConfig":
        """Create config from environment variables."""
        enabled = os.getenv("BACKCHANNELING_ENABLED", "true").lower() == "true"
        
        # Parse custom filler words from env (comma-separated)
        filler_env = os.getenv("BACKCHANNELING_FILLER_WORDS", "")
        if filler_env:
            filler_words = frozenset(w.strip().lower() for w in filler_env.split(",") if w.strip())
        else:
            filler_words = DEFAULT_FILLER_WORDS
        
        # Parse custom command words from env (comma-separated)
        command_env = os.getenv("BACKCHANNELING_COMMAND_WORDS", "")
        if command_env:
            command_words = frozenset(w.strip().lower() for w in command_env.split(",") if w.strip())
        else:
            command_words = DEFAULT_COMMAND_WORDS
        
        return cls(
            enabled=enabled,
            filler_words=filler_words,
            command_words=command_words,
        )


class BackchannelingFilter:
    """
    Intelligent filter for distinguishing backchanneling from real interruptions.
    
    This filter analyzes transcripts in context of whether the agent is speaking
    to determine the appropriate action:
    
    - If agent IS speaking and user says filler word → IGNORE (don't interrupt)
    - If agent IS speaking and user says command word → INTERRUPT
    - If agent is NOT speaking → RESPOND (normal processing)
    """
    
    def __init__(self, config: Optional[BackchannelingConfig] = None):
        self._config = config or BackchannelingConfig.from_env()
        logger.debug(
            "BackchannelingFilter initialized",
            extra={
                "enabled": self._config.enabled,
                "filler_words_count": len(self._config.filler_words),
                "command_words_count": len(self._config.command_words),
            }
        )
    
    @property
    def config(self) -> BackchannelingConfig:
        return self._config
    
    def _normalize(self, text: str) -> str:
        """Normalize text for comparison.
        
        Strips whitespace and punctuation, and optionally lowercases.
        """
        if not self._config.case_sensitive:
            text = text.lower()
        # Strip whitespace
        text = text.strip()
        # Strip common punctuation that STT might add
        text = text.strip(".,!?;:'\"")
        return text
    
    def _contains_command_word(self, words: list[str]) -> bool:
        """Check if any command word is present in the word list."""
        for word in words:
            if word in self._config.command_words:
                return True
        return False
    
    def _is_pure_filler(self, words: list[str], normalized_text: str) -> bool:
        """Check if input is pure filler (backchanneling).
        
        First checks if the full normalized text is a multi-word filler phrase,
        then checks if all individual words are filler words.
        """
        if not words:
            return False
        
        # First check if the full text is a multi-word filler phrase (e.g., "uh huh", "got it")
        if normalized_text in self._config.filler_words:
            return True
        
        # Then check if all individual words are filler words
        return all(word in self._config.filler_words for word in words)
    
    def _is_partial_filler(self, text: str) -> bool:
        """Check if text could be a partial filler word being typed/spoken.
        
        This handles cases where STT sends partial transcripts like "h" or "hm"
        before completing to "hmm".
        """
        text = text.strip().lower()
        if not text or len(text) > 10:  # Too long to be a partial filler
            return False
        
        # Check if any filler word STARTS with this text
        for filler in self._config.filler_words:
            if filler.startswith(text) or text.startswith(filler):
                return True
        return False
    
    def analyze_transcript(
        self,
        transcript: str,
        agent_speaking: bool,
    ) -> BackchannelingResult:
        """
        Analyze a transcript to determine the appropriate action.
        
        Args:
            transcript: The user's speech transcript
            agent_speaking: Whether the agent is currently speaking
            
        Returns:
            BackchannelingResult indicating what to do
        """
        if not self._config.enabled:
            return BackchannelingResult.RESPOND
        
        normalized = self._normalize(transcript)
        
        # Split into words for analysis, stripping punctuation from each word
        words = [w.strip(".,!?;:'\"") for w in normalized.split()] if normalized else []
        words = [w for w in words if w]  # Remove empty strings after stripping
        
        # If agent is NOT speaking, always respond to input  
        if not agent_speaking:
            return BackchannelingResult.RESPOND
        
        # If we have no meaningful words (empty or just punctuation), ignore while speaking
        if not words:
            return BackchannelingResult.IGNORE
        
        # Agent IS speaking - check for commands first (take priority)
        if self._contains_command_word(words):
            logger.debug(
                "Command word detected - will interrupt",
                extra={"transcript": transcript, "words": words}
            )
            return BackchannelingResult.INTERRUPT
        
        # Check if it's pure filler (all words are filler words or multi-word phrase)
        if self._is_pure_filler(words, normalized):
            logger.debug(
                "Pure filler detected - will ignore",
                extra={"transcript": transcript, "words": words}
            )
            return BackchannelingResult.IGNORE
        
        # Check if this might be a partial filler (STT still processing)
        # e.g., "h" or "hm" before "hmm" is complete
        # Only check if using default filler words
        if self._config.filler_words == DEFAULT_FILLER_WORDS and self._is_partial_filler(normalized):
            logger.debug(
                "Partial filler detected - will ignore (waiting for complete transcript)",
                extra={"transcript": transcript, "normalized": normalized}
            )
            return BackchannelingResult.IGNORE
        
        # Mixed content or unknown - let it interrupt to be safe
        logger.debug(
            "Non-filler content detected - will interrupt",
            extra={"transcript": transcript, "words": words}
        )
        return BackchannelingResult.INTERRUPT
    
    def should_ignore_transcript(
        self,
        transcript: str,
        agent_speaking: bool,
    ) -> bool:
        """
        Convenience method to check if a transcript should be ignored.
        
        Returns True if the transcript is backchanneling that should be ignored.
        """
        result = self.analyze_transcript(transcript, agent_speaking)
        return result == BackchannelingResult.IGNORE


# Global filter instance for easy access
_global_filter: Optional[BackchannelingFilter] = None


def get_global_filter() -> BackchannelingFilter:
    """Get the global backchanneling filter instance."""
    global _global_filter
    if _global_filter is None:
        _global_filter = BackchannelingFilter()
    return _global_filter


def set_global_filter(filter_instance: BackchannelingFilter) -> None:
    """Set a custom global backchanneling filter."""
    global _global_filter
    _global_filter = filter_instance


def should_ignore_for_interruption(transcript: str, agent_speaking: bool) -> bool:
    """
    Convenience function to check if a transcript should be ignored for interruption.
    
    This is the main entry point for the backchanneling filter logic.
    
    Args:
        transcript: The user's speech transcript
        agent_speaking: Whether the agent is currently speaking
        
    Returns:
        True if the transcript should be ignored (is backchanneling while agent speaks)
    """
    filter_instance = get_global_filter()
    return filter_instance.should_ignore_transcript(transcript, agent_speaking)

