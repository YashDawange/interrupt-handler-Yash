"""
Interruption Filter for Context-Aware Interruption Handling

This module implements the core logic to distinguish between:
- Passive acknowledgments (backchanneling): "yeah", "ok", "hmm"
- Active interruptions (commands): "stop", "wait", "no"

The filter analyzes user transcriptions and decides whether the agent
should be interrupted based on the current agent state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from ...log import logger


@dataclass
class InterruptionDecision:
    """Result of an interruption decision."""
    
    should_interrupt: bool
    """Whether the agent should be interrupted."""
    
    reason: str
    """Human-readable explanation of the decision."""
    
    confidence: float = 1.0
    """Confidence score for this decision (0.0 - 1.0)."""
    
    classified_as: str = "unknown"
    """Classification: 'backchannel', 'command', 'unknown', or 'mixed'."""


class InterruptionFilter:
    """
    Context-aware filter for determining if user input should interrupt the agent.
    
    Decision Logic:
    - Backchannel words (yeah, ok, hmm) when SPEAKING -> IGNORE
    - Command words (stop, wait, no) when SPEAKING -> INTERRUPT
    - Any input when SILENT -> Process normally
    - Mixed input (has both backchannel and command) -> INTERRUPT
    
    Example:
        >>> filter = InterruptionFilter()
        >>> state = {"is_speaking": True}
        >>> decision, reason = filter.should_interrupt("yeah", state)
        >>> print(decision)  # False (ignore backchannel while speaking)
        
        >>> decision, reason = filter.should_interrupt("stop", state)
        >>> print(decision)  # True (interrupt on command)
    """
    
    def __init__(
        self,
        ignore_words: Optional[list[str]] = None,
        command_words: Optional[list[str]] = None,
        enable_fuzzy_match: bool = True,
        fuzzy_threshold: float = 0.8,
    ) -> None:
        """
        Initialize the interruption filter.
        
        Args:
            ignore_words: List of words to ignore when agent is speaking.
                         Defaults to common backchanneling words.
            command_words: List of words that should trigger interruption.
                          Defaults to common command words.
            enable_fuzzy_match: Enable fuzzy matching for misspellings
                               (default: True).
            fuzzy_threshold: Similarity threshold for fuzzy matching (default: 0.8).
        """
        # Default ignore words (backchanneling)
        self.ignore_words = [
            "yeah",
            "ok",
            "okay",
            "hmm",
            "uh-huh",
            "uhhuh",
            "right",
            "yep",
            "mm-hmm",
            "mhmm",
            "uh",
            "um",
            "sure",
            "got it",
            "gotcha",
            "i hear you",
            "i see",
            "understood",
            "copy that",
            "yup",
            "ya",
        ]
        
        # Default command words (interruptions)
        self.command_words = [
            "stop",
            "wait",
            "no",
            "hold on",
            "hold up",
            "pause",
            "slow down",
            "hold",
            "dont",
            "don't",
            "never mind",
            "never",
            "wrong",
            "nope",
            "cancel",
            "abort",
            "quit",
            "exit",
            "end",
        ]
        
        # Override with user-provided lists
        if ignore_words is not None:
            self.ignore_words = ignore_words
        if command_words is not None:
            self.command_words = command_words
        
        self.enable_fuzzy_match = enable_fuzzy_match
        self.fuzzy_threshold = fuzzy_threshold
        
        # Normalize for faster matching
        self._ignore_words_lower = {w.lower() for w in self.ignore_words}
        self._command_words_lower = {w.lower() for w in self.command_words}
        
        logger.debug(
            f"InterruptionFilter initialized with "
            f"{len(self.ignore_words)} ignore words and "
            f"{len(self.command_words)} command words"
        )
    
    def should_interrupt(
        self,
        text: str,
        agent_state: dict,
    ) -> Tuple[bool, str]:
        """
        Determine if agent should be interrupted based on text and state.
        
        Args:
            text: User's transcribed speech.
            agent_state: Agent state dictionary with 'is_speaking' key.
        
        Returns:
            Tuple[bool, str]: (should_interrupt, reason)
            
        Note:
            Returns the decision as a tuple for backwards compatibility.
            Use should_interrupt_detailed() for more information.
        """
        decision = self.should_interrupt_detailed(text, agent_state)
        return decision.should_interrupt, decision.reason
    
    def should_interrupt_detailed(
        self,
        text: str,
        agent_state: dict,
    ) -> InterruptionDecision:
        """
        Determine if agent should be interrupted (detailed version).
        
        Args:
            text: User's transcribed speech.
            agent_state: Agent state dictionary with 'is_speaking' key.
        
        Returns:
            InterruptionDecision: Detailed decision with classification.
        """
        if not text or not text.strip():
            return InterruptionDecision(
                should_interrupt=False,
                reason="Empty transcription, ignoring",
                classified_as="unknown",
            )
        
        text = text.strip()
        is_speaking = agent_state.get("is_speaking", False)
        
        # Analyze the text
        has_backchannel = self._is_pure_backchannel(text)
        has_command = self._contains_command(text)
        
        # Decision logic
        if has_command and has_backchannel:
            # Mixed: "yeah but wait" -> INTERRUPT
            return InterruptionDecision(
                should_interrupt=True,
                reason=f"Mixed input detected (backchannel + command): '{text}'",
                classified_as="mixed",
            )
        elif has_command:
            # Pure command: always interrupt
            return InterruptionDecision(
                should_interrupt=True,
                reason=f"Command word detected: '{text}'",
                classified_as="command",
            )
        elif has_backchannel:
            if is_speaking:
                # Backchannel while agent speaking -> IGNORE
                return InterruptionDecision(
                    should_interrupt=False,
                    reason=f"Backchannel detected while agent speaking, ignoring: '{text}'",
                    classified_as="backchannel",
                )
            else:
                # Backchannel while silent -> PROCESS
                return InterruptionDecision(
                    should_interrupt=False,
                    reason=f"Backchannel while silent, processing as input: '{text}'",
                    classified_as="backchannel",
                )
        else:
            # Unknown text -> PROCESS (safe default)
            return InterruptionDecision(
                should_interrupt=False,
                reason=f"No command or backchannel detected: '{text}'",
                classified_as="unknown",
            )
    
    def _is_pure_backchannel(self, text: str) -> bool:
        """
        Check if text contains only backchannel words.
        
        Args:
            text: User's transcribed speech.
        
        Returns:
            bool: True if text is pure backchannel, False otherwise.
        """
        normalized = self._normalize_text(text)
        
        # Check for exact matches
        if normalized in self._ignore_words_lower:
            return True
        
        # Check if all tokens are backchannels
        tokens = normalized.split()
        if not tokens:
            return False
        
        # All tokens must be backchannels
        return all(token in self._ignore_words_lower for token in tokens)
    
    def _contains_command(self, text: str) -> bool:
        """
        Check if text contains command words.
        
        Args:
            text: User's transcribed speech.
        
        Returns:
            bool: True if text contains command words, False otherwise.
        """
        normalized = self._normalize_text(text)
        
        # Check for exact matches
        if normalized in self._command_words_lower:
            return True
        
        # Check if any token is a command
        tokens = normalized.split()
        for token in tokens:
            if token in self._command_words_lower:
                return True
            
            # Fuzzy matching for misspellings/variations
            if self.enable_fuzzy_match:
                for cmd in self._command_words_lower:
                    if self._fuzzy_match(token, cmd):
                        return True
        
        return False
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.
        
        Args:
            text: Text to normalize.
        
        Returns:
            str: Normalized text (lowercase, cleaned).
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation (but keep hyphens and apostrophes)
        text = re.sub(r"[^\w\s\-']", "", text)
        
        # Remove extra whitespace
        text = " ".join(text.split())
        
        return text
    
    def _fuzzy_match(self, text: str, target: str, threshold: Optional[float] = None) -> bool:
        """
        Simple fuzzy matching for typos/variations.
        
        Uses a basic similarity score (Levenshtein-like).
        
        Args:
            text: Text to match.
            target: Target to match against.
            threshold: Similarity threshold (default: self.fuzzy_threshold).
        
        Returns:
            bool: True if similarity >= threshold.
        """
        if threshold is None:
            threshold = self.fuzzy_threshold
        
        # Simple: if texts are within 1-2 character edits
        # For more accuracy, use python-Levenshtein library
        if len(text) == 0 or len(target) == 0:
            return False
        
        similarity = self._levenshtein_similarity(text, target)
        return similarity >= threshold
    
    @staticmethod
    def _levenshtein_similarity(s1: str, s2: str) -> float:
        """
        Calculate Levenshtein similarity score (0.0 - 1.0).
        
        Args:
            s1: First string.
            s2: Second string.
        
        Returns:
            float: Similarity score (1.0 = identical, 0.0 = completely different).
        """
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Create distance matrix
        d = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        for i in range(len1 + 1):
            d[i][0] = i
        for j in range(len2 + 1):
            d[0][j] = j
        
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                d[i][j] = min(
                    d[i - 1][j] + 1,
                    d[i][j - 1] + 1,
                    d[i - 1][j - 1] + cost,
                )
        
        max_len = max(len1, len2)
        distance = d[len1][len2]
        
        # Convert distance to similarity (0-1 scale)
        return 1.0 - (distance / max_len)
    
    def update_ignore_words(self, words: list[str]) -> None:
        """
        Update the list of ignore words (backchanneling).
        
        Args:
            words: New list of ignore words.
        """
        self.ignore_words = words
        self._ignore_words_lower = {w.lower() for w in words}
        logger.info(f"Updated ignore words ({len(words)} total)")
    
    def update_command_words(self, words: list[str]) -> None:
        """
        Update the list of command words (interruptions).
        
        Args:
            words: New list of command words.
        """
        self.command_words = words
        self._command_words_lower = {w.lower() for w in words}
        logger.info(f"Updated command words ({len(words)} total)")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"InterruptionFilter("
            f"ignore_words={len(self.ignore_words)}, "
            f"command_words={len(self.command_words)})"
        )
