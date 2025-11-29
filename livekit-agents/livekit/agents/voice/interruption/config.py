"""Configuration for semantic interruption handling."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InterruptionConfig:
    """Configuration for semantic interruption handling.
    
    This configuration controls how the agent handles user speech while it is speaking.
    
    Attributes:
        ignore_words: Set of backchannel words to ignore while agent is speaking.
            These words will not interrupt the agent or create user turns.
            Default: Common English backchannel tokens.
        
        command_words: Set of command words that always trigger interruption.
            When detected, these words will stop the agent immediately.
            Default: Common interruption commands.
        
        command_phrases: Set of multi-word command phrases that trigger interruption.
            These are checked before individual tokens.
            Default: Common multi-word interruption phrases.
        
        interrupt_on_normal_content: Whether to interrupt when user says substantive
            content (questions, statements) while agent is speaking.
            - True (default): Any non-backchannel utterance interrupts the agent,
              just like explicit commands. This matches natural conversation flow.
            - False: Only explicit commands interrupt. Normal content is ignored
              while agent is speaking (not recommended for most use cases).
    
    Example:
        >>> # Use defaults
        >>> config = InterruptionConfig()
        >>> 
        >>> # Customize for specific use case
        >>> config = InterruptionConfig(
        ...     ignore_words={"yeah", "ok", "mmhmm"},
        ...     command_words={"stop", "wait", "pause"},
        ...     interrupt_on_normal_content=False,  # Only commands interrupt
        ... )
    """
    
    ignore_words: set[str] = field(default_factory=lambda: {
        "yeah", "ok", "okay", "hmm", "mm", "uh", "uh-huh", "mm-hmm",
        "right", "sure", "yep", "yup", "mhm", "ah", "oh"
    })
    """Backchannel words to ignore while agent is speaking."""
    
    command_words: set[str] = field(default_factory=lambda: {
        "stop", "wait", "no", "pause", "hold", "hang", "interrupt"
    })
    """Command words that always trigger interruption."""
    
    command_phrases: set[str] = field(default_factory=lambda: {
        "wait a second", "hold on", "hang on", "wait up",
        "stop it", "hold up", "wait a minute", "one second",
        "just a second", "hang on a second"
    })
    """Multi-word command phrases that trigger interruption."""
    
    interrupt_on_normal_content: bool = True
    """Whether normal content (questions, statements) interrupts while agent speaking.
    
    By default, any substantive utterance while the agent is speaking will interrupt,
    just like commands. To make only explicit commands interrupt, set this to False.
    """
