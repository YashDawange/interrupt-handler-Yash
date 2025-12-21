"""
Interrupt Filter - Core logic for intelligent interruption handling.

This module contains the main InterruptFilter class that analyzes transcripts
and determines whether they should interrupt the agent or be ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

try:
    from .wordlists import DEFAULT_IGNORE_WORDS, DEFAULT_INTERRUPT_WORDS
except ImportError:
    from wordlists import DEFAULT_IGNORE_WORDS, DEFAULT_INTERRUPT_WORDS

# Decision types for interrupt filtering
InterruptDecision = Literal["ignore", "interrupt", "respond"]


@dataclass
class InterruptFilterConfig:
    """
    Configuration for the intelligent interrupt filter.
    
    Attributes:
        ignore_words: Set of words to ignore when agent is speaking
        interrupt_words: Set of words that always trigger interruption
        case_sensitive: Whether word matching is case-sensitive
        partial_match: Whether to match partial words (e.g., "yeah" in "yeahhhh")
    
    Example:
        # Default config
        config = InterruptFilterConfig()
        
        # Custom config
        config = InterruptFilterConfig(
            ignore_words=frozenset(["yeah", "ok", "sure"]),
            interrupt_words=frozenset(["stop", "wait", "no"]),
        )
    """
    ignore_words: frozenset[str] = field(default_factory=lambda: DEFAULT_IGNORE_WORDS)
    interrupt_words: frozenset[str] = field(default_factory=lambda: DEFAULT_INTERRUPT_WORDS)
    case_sensitive: bool = False
    partial_match: bool = True
    
    @classmethod
    def from_env(cls) -> "InterruptFilterConfig":
        """
        Create config from environment variables.
        
        Environment variables:
            IGNORE_WORDS: Comma-separated list of words to ignore
            INTERRUPT_WORDS: Comma-separated list of words that trigger interrupt
        """
        try:
            from .wordlists import load_wordlist_from_env
        except ImportError:
            from wordlists import load_wordlist_from_env
        
        return cls(
            ignore_words=load_wordlist_from_env("IGNORE_WORDS", DEFAULT_IGNORE_WORDS),
            interrupt_words=load_wordlist_from_env("INTERRUPT_WORDS", DEFAULT_INTERRUPT_WORDS),
        )
    
    @classmethod
    def for_domain(
        cls,
        domain: str,
        additional_ignore: frozenset[str] | None = None,
        additional_interrupt: frozenset[str] | None = None,
    ) -> "InterruptFilterConfig":
        """
        Create a domain-specific config with extended wordlists.
        
        Args:
            domain: Domain name for identification
            additional_ignore: Extra words to add to ignore list
            additional_interrupt: Extra words to add to interrupt list
        """
        try:
            from .wordlists import create_domain_wordlist
        except ImportError:
            from wordlists import create_domain_wordlist
        
        ignore, interrupt = create_domain_wordlist(
            domain,
            additional_ignore=additional_ignore,
            additional_interrupt=additional_interrupt,
        )
        return cls(ignore_words=ignore, interrupt_words=interrupt)


@dataclass
class InterruptAnalysis:
    """
    Result of analyzing user input for interruption.
    
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
    
    def __str__(self) -> str:
        return f"InterruptAnalysis({self.decision}: {self.reason})"
    
    @property
    def should_interrupt(self) -> bool:
        """Returns True if agent should stop speaking."""
        return self.decision in ("interrupt", "respond")
    
    @property
    def should_ignore(self) -> bool:
        """Returns True if input should be ignored."""
        return self.decision == "ignore"


class InterruptFilter:
    """
    Intelligent interrupt filter that distinguishes between passive acknowledgements
    and active interruptions based on agent state and transcript content.
    
    The filter follows this decision tree:
    
    1. If agent is NOT speaking → Always "respond" to user input
    2. If agent IS speaking:
       a. Check for interrupt words → "interrupt"
       b. Check if only filler words → "ignore"
       c. Check for substantive content → "interrupt"
       d. Default → "ignore"
    
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
        """
        Initialize the interrupt filter.
        
        Args:
            config: Filter configuration. Uses defaults if not provided.
        """
        self.config = config or InterruptFilterConfig()
        self._build_lookup_sets()
    
    def _build_lookup_sets(self) -> None:
        """Build O(1) lookup sets for fast matching."""
        # Normalize all words to lowercase for O(1) set lookups
        self._ignore_set: set[str] = {
            w.lower() for w in self.config.ignore_words
        }
        self._interrupt_set: set[str] = {
            w.lower() for w in self.config.interrupt_words
        }
        
        # For multi-word phrases, store them separately
        self._ignore_phrases: set[str] = {
            w.lower() for w in self.config.ignore_words if ' ' in w
        }
        self._interrupt_phrases: set[str] = {
            w.lower() for w in self.config.interrupt_words if ' ' in w
        }
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for analysis."""
        # Remove punctuation and normalize whitespace
        text = re.sub(r'[.,!?;:]+', ' ', text)
        return ' '.join(text.lower().split())
    
    def _find_ignore_words(self, text: str, words: list[str]) -> list[str]:
        """Find all ignore words in the text using O(1) set lookup."""
        matched = []
        
        # O(1) lookup for single words
        for word in words:
            if word in self._ignore_set:
                matched.append(word)
        
        # Check multi-word phrases (still fast - small set)
        for phrase in self._ignore_phrases:
            if phrase in text:
                matched.append(phrase)
        
        return matched
    
    def _find_interrupt_words(self, text: str, words: list[str]) -> list[str]:
        """Find all interrupt words in the text using O(1) set lookup."""
        matched = []
        
        # O(1) lookup for single words
        for word in words:
            if word in self._interrupt_set:
                matched.append(word)
        
        # Check multi-word phrases (still fast - small set)
        for phrase in self._interrupt_phrases:
            if phrase in text:
                matched.append(phrase)
        
        return matched
    
    def _is_only_filler(self, words: list[str]) -> bool:
        """Check if all words are filler words using O(1) lookups."""
        for word in words:
            if word not in self._ignore_set:
                return False
        return len(words) > 0
    
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
        words = normalized.split()
        
        # O(1) lookups using sets
        ignore_matches = self._find_ignore_words(normalized, words)
        interrupt_matches = self._find_interrupt_words(normalized, words)
        
        # Case 1: Agent is NOT speaking - always respond
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
        
        # 2a: Interrupt words take priority
        if interrupt_matches:
            return InterruptAnalysis(
                decision="interrupt",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason=f"Found interrupt command words: {interrupt_matches}"
            )
        
        # 2b: Only filler words - ignore (O(1) per word)
        if self._is_only_filler(words):
            return InterruptAnalysis(
                decision="ignore",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason=f"Only filler words detected: {ignore_matches}"
            )
        
        # 2c: Check for substantive content (O(1) per word)
        non_filler_words = [w for w in words if w not in self._ignore_set]
        
        if len(non_filler_words) > min_words_for_content:
            return InterruptAnalysis(
                decision="interrupt",
                transcript=transcript,
                agent_was_speaking=True,
                matched_ignore_words=ignore_matches,
                matched_interrupt_words=interrupt_matches,
                reason=f"Contains substantive content: {non_filler_words}"
            )
        
        # 2d: Default to ignore
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
        """
        return self.analyze(transcript, agent_speaking).should_interrupt
    
    def should_ignore(self, transcript: str, agent_speaking: bool) -> bool:
        """
        Check if the input should be ignored.
        
        Returns True only when agent is speaking AND transcript is filler.
        """
        return self.analyze(transcript, agent_speaking).should_ignore
