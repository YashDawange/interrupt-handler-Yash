"""Configuration for semantic interruption handling."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class InterruptionConfig:
    """Configuration for semantic interruption handling.
    
    Attributes:
        ignore_words: Set of backchannel words to ignore while agent is speaking.
        command_words: Set of command words that always trigger interruption.
        command_phrases: Set of multi-word command phrases that trigger interruption.
        interrupt_on_normal_content: Whether to interrupt when user says substantive
            content (questions, statements) while agent is speaking.
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
    
    @classmethod
    def from_env(cls) -> InterruptionConfig:
        """Create configuration from environment variables.
        
        Environment variables:
            INTERRUPTION_IGNORE_WORDS: Comma-separated list of backchannel words
            INTERRUPTION_COMMAND_WORDS: Comma-separated list of command words
            INTERRUPTION_COMMAND_PHRASES: Comma-separated list of command phrases
            INTERRUPTION_INTERRUPT_ON_NORMAL: "true" or "false"
        """
        # Parse comma-separated lists from environment
        def parse_word_list(env_var: str, default: set[str]) -> set[str]:
            """Parse comma-separated word list from environment."""
            value = os.getenv(env_var)
            if not value:
                return default
            return {w.strip().lower() for w in value.split(",") if w.strip()}
        
        # Parse boolean from environment
        def parse_bool(env_var: str, default: bool) -> bool:
            """Parse boolean from environment (true/false, 1/0, yes/no)."""
            value = os.getenv(env_var)
            if not value:
                return default
            return value.lower() in ("true", "1", "yes", "on")
        
        # Create default config to get defaults
        default_config = cls()
        
        return cls(
            ignore_words=parse_word_list(
                "INTERRUPTION_IGNORE_WORDS",
                default_config.ignore_words
            ),
            command_words=parse_word_list(
                "INTERRUPTION_COMMAND_WORDS",
                default_config.command_words
            ),
            command_phrases=parse_word_list(
                "INTERRUPTION_COMMAND_PHRASES",
                default_config.command_phrases
            ),
            interrupt_on_normal_content=parse_bool(
                "INTERRUPTION_INTERRUPT_ON_NORMAL",
                default_config.interrupt_on_normal_content
            ),
        )
