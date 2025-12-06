"""
Backchannel Filter for Intelligent Interruption Handling.

This module provides context-aware filtering to distinguish between:
- Passive acknowledgements ("yeah", "ok", "hmm") that should be ignored while agent speaks
- Active interruptions ("stop", "wait", "no") that should interrupt the agent
- Normal input when agent is silent (always process)

Usage:
    from livekit.agents.voice.backchannel_filter import BackchannelFilter, BackchannelConfig
    
    filter = BackchannelFilter()
    should_ignore = filter.should_ignore("yeah", agent_is_speaking=True)  # True
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BackchannelConfig:
    """
    Configuration for backchannel filtering.
    
    Attributes:
        ignore_words: Words to ignore when agent is speaking (passive acknowledgements).
        interrupt_words: Words that always trigger interruption (override ignore_words).
        enabled: Whether the filter is active.
    """
    
    # Words to IGNORE when agent is speaking (backchannels/fillers)
    ignore_words: set[str] = field(default_factory=lambda: {
        # Affirmations
        "yeah", "yea", "yes", "yep", "yup",
        # Acknowledgements
        "ok", "okay", "alright", "right", "sure", "fine",
        # Fillers/listening signals
        "hmm", "mm", "mmm", "mhm", "mhmm", "uh-huh", "uh huh", "uhuh", "aha", "hm",
        # Understanding signals
        "gotcha", "got it", "i see", "understood",
    })
    
    # Words that ALWAYS trigger interrupt (even if mixed with ignore words)
    interrupt_words: set[str] = field(default_factory=lambda: {
        # Stop commands
        "stop", "wait", "pause", "hold on", "hold up", "hang on",
        # Negation/correction
        "no", "nope", "actually", "but", "however",
        # Attention grabbers
        "excuse me", "hey", "listen",
    })
    
    enabled: bool = True


class BackchannelFilter:
    """
    Filters user speech to distinguish passive acknowledgements from real interruptions.
    
    Logic Matrix:
        | User Input          | Agent State | Result              |
        |---------------------|-------------|---------------------|
        | "yeah", "ok", "hmm" | Speaking    | IGNORE (return True)|
        | "stop", "wait"      | Speaking    | INTERRUPT (False)   |
        | "yeah wait"         | Speaking    | INTERRUPT (False)   |
        | any input           | Silent      | RESPOND (False)     |
    
    Example:
        >>> filter = BackchannelFilter()
        >>> filter.should_ignore("yeah", agent_is_speaking=True)
        True
        >>> filter.should_ignore("yeah", agent_is_speaking=False)
        False
        >>> filter.should_ignore("stop", agent_is_speaking=True)
        False
    """
    
    def __init__(self, config: BackchannelConfig | None = None) -> None:
        """
        Initialize the backchannel filter.
        
        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or BackchannelConfig()
    
    def should_ignore(self, transcript: str, agent_is_speaking: bool) -> bool:
        """
        Determine if the user input should be ignored (not trigger interruption).
        
        Args:
            transcript: The transcribed user speech.
            agent_is_speaking: Whether the agent is currently speaking.
            
        Returns:
            True if the input should be IGNORED (agent continues speaking).
            False if the input should be PROCESSED (may interrupt agent).
        """
        if not self.config.enabled:
            return False
        
        # Agent is silent → always process input (never ignore)
        if not agent_is_speaking:
            return False
        
        # Agent is speaking → check content
        normalized = transcript.lower().strip()
        
        if not normalized:
            return False
        
        # Check for interrupt commands first (takes priority)
        if self._contains_interrupt_word(normalized):
            return False  # Don't ignore - this is a real interruption
        
        # Check if input consists ONLY of backchannel words
        if self._is_backchannel_only(normalized):
            return True  # Ignore - just passive acknowledgement
        
        # Default: don't ignore (process as potential interruption)
        return False
    
    def _contains_interrupt_word(self, text: str) -> bool:
        """
        Check if text contains any interrupt command.
        
        Handles both single words and multi-word phrases.
        
        Args:
            text: Normalized (lowercase) transcript text.
            
        Returns:
            True if any interrupt word/phrase is found.
        """
        for word in self.config.interrupt_words:
            if word in text:
                return True
        return False
    
    def _is_backchannel_only(self, text: str) -> bool:
        """
        Check if text contains ONLY backchannel/filler words.
        
        Args:
            text: Normalized (lowercase) transcript text.
            
        Returns:
            True if all words in the text are backchannel words.
        """
        # Split into words, handling basic punctuation
        words = set(text.replace(",", " ").replace(".", " ").replace("!", " ").split())
        
        if not words:
            return False
        
        # Check if every word is in the ignore list
        return words.issubset(self.config.ignore_words)
    
    def contains_interrupt_command(self, transcript: str) -> bool:
        """
        Public method to check if transcript contains explicit interrupt commands.
        
        Args:
            transcript: The user's transcribed speech.
            
        Returns:
            True if an interrupt command is present.
        """
        return self._contains_interrupt_word(transcript.lower().strip())
    
    def is_backchannel_only(self, transcript: str) -> bool:
        """
        Public method to check if transcript contains only backchannel words.
        
        Args:
            transcript: The user's transcribed speech.
            
        Returns:
            True if only backchannel words are present.
        """
        return self._is_backchannel_only(transcript.lower().strip())
