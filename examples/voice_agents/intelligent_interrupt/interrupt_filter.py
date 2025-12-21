"""
Intelligent Interruption Filter Module

This module provides context-aware interruption filtering for LiveKit voice agents.
It distinguishes between "passive acknowledgements" (yeah, ok, hmm) and 
"active interruptions" (stop, wait, no) based on the agent's current speaking state.

Key Features:
- Configurable ignore list for filler words
- State-based filtering (only filters when agent is speaking)
- Semantic detection for command words in mixed sentences
- Real-time, low-latency decision making
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Literal

# Default list of words to ignore when agent is speaking
# These are common "backchanneling" words that indicate listening, not interruption
DEFAULT_IGNORE_WORDS = frozenset([
    # English acknowledgements
    "yeah", "yes", "yep", "yup", "ya",
    "ok", "okay", "k",
    "hmm", "hm", "hmm-hmm", "hmmm",
    "uh-huh", "uh huh", "uhuh", "uhhuh",
    "mm-hmm", "mm hmm", "mmhmm", "mhm",
    "right", "alright",
    "sure", "aha", "ah",
    "i see", "got it", "gotcha",
    "cool", "nice", "great",
    # Common filler sounds
    "um", "uh", "er",
])

# Words that should ALWAYS trigger an interrupt, even if mixed with filler words
DEFAULT_INTERRUPT_WORDS = frozenset([
    "stop", "wait", "hold", "pause",
    "no", "nope", "cancel", "quit",
    "actually", "but", "however",
    "question", "ask",
    "excuse", "sorry",
    "repeat", "again",
    "help", "what",
    "hang on", "one second", "just a moment",
])


@dataclass
class InterruptFilterConfig:
    """Configuration for the intelligent interrupt filter.
    
    Attributes:
        ignore_words: Set of words to ignore when agent is speaking
        interrupt_words: Set of words that always trigger interruption
        case_sensitive: Whether word matching is case-sensitive
        partial_match: Whether to match partial words (e.g., "yeah" in "yeahhhh")
    """
    ignore_words: frozenset[str] = field(default_factory=lambda: DEFAULT_IGNORE_WORDS)
    interrupt_words: frozenset[str] = field(default_factory=lambda: DEFAULT_INTERRUPT_WORDS)
    case_sensitive: bool = False
    partial_match: bool = True
    
    @classmethod
    def from_env(cls) -> "InterruptFilterConfig":
        """Create config from environment variables.
        
        Environment variables:
            IGNORE_WORDS: Comma-separated list of words to ignore
            INTERRUPT_WORDS: Comma-separated list of words that trigger interrupt
        """
        import os
        
        ignore_words = DEFAULT_IGNORE_WORDS
        interrupt_words = DEFAULT_INTERRUPT_WORDS
        
        if env_ignore := os.getenv("IGNORE_WORDS"):
            ignore_words = frozenset(w.strip().lower() for w in env_ignore.split(","))
        
        if env_interrupt := os.getenv("INTERRUPT_WORDS"):
            interrupt_words = frozenset(w.strip().lower() for w in env_interrupt.split(","))
        
        return cls(ignore_words=ignore_words, interrupt_words=interrupt_words)


# Decision types for interrupt filtering
InterruptDecision = Literal["ignore", "interrupt", "respond"]


@dataclass
class InterruptAnalysis:
    """Result of analyzing user input for interruption.
    
    Attributes:
        decision: The decision made (ignore, interrupt, or respond)
        transcript: The analyzed transcript
        agent_was_speaking: Whether agent was speaking when input received
        matched_ignore_words: List of ignore words found in transcript
        matched_interrupt_words: List of interrupt words found in transcript
        reason: Human-readable explanation of the decision
    """
    decision: InterruptDecision
    transcript: str
    agent_was_speaking: bool
    matched_ignore_words: list[str] = field(default_factory=list)
    matched_interrupt_words: list[str] = field(default_factory=list)
    reason: str = ""


class InterruptFilter:
    """
    Intelligent interrupt filter that distinguishes between passive acknowledgements
    and active interruptions based on agent state and transcript content.
    
    Usage:
        filter = InterruptFilter()
        
        # When agent is speaking and user says "yeah"
        analysis = filter.analyze("yeah", agent_speaking=True)
        # analysis.decision == "ignore"
        
        # When agent is silent and user says "yeah"
        analysis = filter.analyze("yeah", agent_speaking=False)
        # analysis.decision == "respond"
        
        # When agent is speaking and user says "yeah but wait"
        analysis = filter.analyze("yeah but wait", agent_speaking=True)
        # analysis.decision == "interrupt"
    """
    
    def __init__(self, config: InterruptFilterConfig | None = None):
        """Initialize the interrupt filter.
        
        Args:
            config: Filter configuration. Uses defaults if not provided.
        """
        self.config = config or InterruptFilterConfig()
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        flags = 0 if self.config.case_sensitive else re.IGNORECASE
        
        # Create word boundary patterns
        if self.config.partial_match:
            # Match word anywhere in text
            self._ignore_pattern = re.compile(
                r'\b(' + '|'.join(re.escape(w) for w in self.config.ignore_words) + r')\b',
                flags
            )
            self._interrupt_pattern = re.compile(
                r'\b(' + '|'.join(re.escape(w) for w in self.config.interrupt_words) + r')\b',
                flags
            )
        else:
            # Exact match only
            self._ignore_pattern = re.compile(
                r'^(' + '|'.join(re.escape(w) for w in self.config.ignore_words) + r')$',
                flags
            )
            self._interrupt_pattern = re.compile(
                r'^(' + '|'.join(re.escape(w) for w in self.config.interrupt_words) + r')$',
                flags
            )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for analysis."""
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove common punctuation that doesn't affect meaning
        text = re.sub(r'[.,!?;:]+', ' ', text)
        text = ' '.join(text.split())
        return text
    
    def _find_ignore_words(self, text: str) -> list[str]:
        """Find all ignore words in the text."""
        return [m.group() for m in self._ignore_pattern.finditer(text)]
    
    def _find_interrupt_words(self, text: str) -> list[str]:
        """Find all interrupt words in the text."""
        return [m.group() for m in self._interrupt_pattern.finditer(text)]
    
    def _is_only_filler(self, text: str) -> bool:
        """Check if text contains only filler/acknowledgement words."""
        normalized = self._normalize_text(text)
        
        # Remove all ignore words and see what's left
        remaining = self._ignore_pattern.sub('', normalized)
        remaining = ' '.join(remaining.split())
        
        # If nothing substantial remains, it's only filler
        return len(remaining) == 0 or remaining.isspace()
    
    def analyze(
        self, 
        transcript: str, 
        agent_speaking: bool,
        min_words_for_content: int = 0
    ) -> InterruptAnalysis:
        """
        Analyze a transcript to determine whether it should interrupt the agent.
        
        Args:
            transcript: The user's speech transcript
            agent_speaking: Whether the agent is currently speaking
            min_words_for_content: Minimum non-filler words needed to consider as content
        
        Returns:
            InterruptAnalysis with the decision and reasoning
        """
        normalized = self._normalize_text(transcript)
        
        ignore_matches = self._find_ignore_words(normalized)
        interrupt_matches = self._find_interrupt_words(normalized)
        
        # Case 1: Agent is NOT speaking - always respond to user input
        if not agent_speaking:
            return InterruptAnalysis(
                decision="respond",
                transcript=transcript,
                agent_was_speaking=False,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason="Agent is silent, treating as valid input"
            )
        
        # Case 2: Agent IS speaking
        
        # 2a: If there are interrupt words, always interrupt
        if interrupt_matches:
            return InterruptAnalysis(
                decision="interrupt",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason=f"Found interrupt command words: {interrupt_matches}"
            )
        
        # 2b: If transcript is only filler words, ignore
        if self._is_only_filler(normalized):
            return InterruptAnalysis(
                decision="ignore",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason=f"Only filler words detected: {ignore_matches}"
            )
        
        # 2c: Check word count for substantive content
        words = normalized.split()
        non_filler_words = [
            w for w in words 
            if not self._ignore_pattern.fullmatch(w)
        ]
        
        if len(non_filler_words) > min_words_for_content:
            return InterruptAnalysis(
                decision="interrupt",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason=f"Contains substantive content: {non_filler_words}"
            )
        
        # 2d: Default to ignore if not enough content
        return InterruptAnalysis(
            decision="ignore",
            transcript=transcript,
            agent_was_speaking=True,
            matched_ignore_words=ignore_matches,
            matched_interrupt_words=interrupt_matches,
            reason="Insufficient substantive content to interrupt"
        )
    
    def should_interrupt(self, transcript: str, agent_speaking: bool) -> bool:
        """
        Simple boolean check for whether to interrupt.
        
        Returns True if the agent should stop and listen.
        Returns False if the agent should continue speaking.
        """
        analysis = self.analyze(transcript, agent_speaking)
        return analysis.decision in ("interrupt", "respond")
    
    def should_ignore(self, transcript: str, agent_speaking: bool) -> bool:
        """
        Check if the input should be ignored.
        
        Returns True only when:
        - Agent is speaking AND
        - Transcript contains only filler/acknowledgement words
        """
        analysis = self.analyze(transcript, agent_speaking)
        return analysis.decision == "ignore"


# Singleton instance with default config
_default_filter: InterruptFilter | None = None


def get_default_filter() -> InterruptFilter:
    """Get the default interrupt filter singleton."""
    global _default_filter
    if _default_filter is None:
        _default_filter = InterruptFilter()
    return _default_filter


def set_default_filter(filter: InterruptFilter) -> None:
    """Set the default interrupt filter singleton."""
    global _default_filter
    _default_filter = filter
