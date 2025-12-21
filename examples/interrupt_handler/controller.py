"""
Intelligent Interruption Controller (Production-Ready)

This module implements a semantic filter for user speech that decides whether to:
- IGNORE: Clear the transcript (backchannel words like "yeah", "ok")
- INTERRUPT: Stop the agent immediately (command words like "stop", "wait")
- NO_DECISION: Let the framework handle normally (substantive input)

The controller tracks agent state to make context-aware decisions:
- When agent is speaking: "yeah" = backchannel (IGNORE)
- When agent is silent: "yeah" = agreement/acknowledgment (NO_DECISION)

Production Fixes Applied:
- Fix #1: Hyphen normalization ("uh-huh" → "uh huh")
- Fix #2: Multi-word phrase matching ("i see", "got it")
- Fix #3: Grace period for state transitions (500ms window)
- Fix #4: Question words in INTERRUPT_WORDS
"""

import logging
import re
import time
from enum import Enum, auto
from typing import Set

logger = logging.getLogger("interrupt-controller")


class Decision(Enum):
    """Decision returned by the InterruptionController."""
    
    IGNORE = auto()
    """Clear user turn, drop transcript from LLM buffer."""
    
    INTERRUPT = auto()
    """Stop agent immediately, user wants the floor."""
    
    NO_DECISION = auto()
    """Let framework handle normally (e.g., when agent is silent)."""


# Backchannel words that should be ignored when agent is speaking
# Using Set for O(1) lookup performance
IGNORE_WORDS: Set[str] = {
    # Single-word backchannels
    "yeah", "yep", "yes", "yup", "yea",
    "ok", "okay", "k",
    "hmm", "hm", "mm", "mhm", "huh"
    "uh", "um", "er", "ah", "oh",
    "right", "sure", "alright",
    "cool", "nice", "great", "good", "fine",
    "thanks", "thx",
    
    # Multi-word backchannels (normalized form - hyphens become spaces)
    "uh huh",      # "uh-huh" → "uh huh" after normalization
    "mm hmm",      # "mm-hmm" → "mm hmm" after normalization
    "all right",
    "got it",
    "gotcha", 
    "i see",
    "makes sense",
    "thank you",
    "no problem", "np",
    
    
}

# Command words that should trigger immediate interruption
INTERRUPT_WORDS: Set[str] = {
    # Stop commands
    "stop", "wait", "pause", "hold", "cancel",
    
    # Multi-word stop commands
    "hold on", "hang on", "wait wait",
    "one moment", "one sec", "one second",
    "never mind", "nevermind",
    
    # Negation/correction
    "no", "actually", "but", "however",
    
    # Silence commands
    "quiet", "shut up", "silence", "enough",
    
    # Question/clarification words (Fix #4)
    "what", "pardon", "sorry",
    "excuse me",
}

# Grace period in seconds after agent stops speaking
# Handles STT latency (transcripts arrive 200-800ms after speech)
GRACE_PERIOD_SECONDS = 0.5


class InterruptionController:
    """
    Intelligent controller for managing speech interruptions.
    
    Implements a semantic filter that analyzes user transcripts and decides
    whether to ignore, interrupt, or let the framework handle the input.
    
    Production Features:
        - Hyphen normalization for compound words ("uh-huh")
        - Multi-word phrase matching ("i see", "got it")
        - Grace period tracking for state transitions
        - O(1) set lookups for performance
    
    Usage:
        controller = InterruptionController()
        
        @session.on("agent_state_changed")
        def on_state_changed(ev):
            controller.update_agent_state(ev.new_state)
        
        @session.on("user_input_transcribed")
        def on_transcript(ev):
            decision = controller.decide(ev.transcript, ev.is_final)
            if decision == Decision.IGNORE:
                session.clear_user_turn()
            elif decision == Decision.INTERRUPT:
                session.interrupt()
    """
    
    def __init__(
        self,
        ignore_words: Set[str] | None = None,
        interrupt_words: Set[str] | None = None,
        grace_period: float = GRACE_PERIOD_SECONDS,
    ) -> None:
        """
        Initialize the controller.
        
        Args:
            ignore_words: Custom set of backchannel words to ignore.
            interrupt_words: Custom set of command words that trigger interruption.
            grace_period: Seconds to wait after agent stops speaking before
                         treating input as normal (handles STT latency).
        """
        self._ignore_words = ignore_words if ignore_words is not None else IGNORE_WORDS
        self._interrupt_words = interrupt_words if interrupt_words is not None else INTERRUPT_WORDS
        self._agent_speaking = False
        self._grace_period = grace_period
        self._last_speaking_end_time: float = 0.0  # Fix #3: Track when speaking stopped
        
        logger.debug(
            f"InterruptionController initialized with "
            f"{len(self._ignore_words)} ignore words, "
            f"{len(self._interrupt_words)} interrupt words, "
            f"{self._grace_period}s grace period"
        )
    
    @property
    def agent_speaking(self) -> bool:
        """Whether the agent is currently speaking."""
        return self._agent_speaking
    
    def update_agent_state(self, new_state: str) -> None:
        """
        Update the controller's knowledge of agent state.
        
        Tracks when agent stops speaking for grace period calculations.
        
        Args:
            new_state: The new agent state ('speaking', 'listening', 'thinking', 'idle')
        """
        old_speaking = self._agent_speaking
        self._agent_speaking = new_state == "speaking"
        
        # Fix #3: Track when agent stops speaking for grace period
        if old_speaking and not self._agent_speaking:
            self._last_speaking_end_time = time.time()
            logger.debug("Agent stopped speaking, grace period active")
        
        if old_speaking != self._agent_speaking:
            logger.debug(f"Agent speaking: {old_speaking} → {self._agent_speaking}")
    
    def _is_effectively_speaking(self) -> bool:
        """
        Check if agent is speaking OR just stopped (within grace period).
        
        Fix #3: Grace period handles STT latency.
        
        WHY NEEDED:
            STT transcripts arrive ~200-800ms after actual speech.
            User might say "stop" at t=5.0s while agent speaking,
            but agent finishes at t=5.1s and transcript arrives at t=5.3s.
            Without grace period, we'd treat "stop" as NO_DECISION.
        
        Returns:
            True if agent is speaking or within grace period after stopping
        """
        if self._agent_speaking:
            return True
        
        # Check grace period
        time_since_stopped = time.time() - self._last_speaking_end_time
        
        if time_since_stopped < self._grace_period:
            logger.debug(f"Grace period active: {time_since_stopped:.2f}s since stop")
            return True
        
        return False
    
    def decide(self, transcript: str, is_final: bool) -> Decision:
        """
        Analyze a transcript and decide how to handle it.
        
        Priority order:
        1. Empty string → IGNORE
        2. Agent is silent (outside grace period) → NO_DECISION
        3. Contains interrupt word → INTERRUPT
        4. Only filler words → IGNORE
        5. Substantive content → INTERRUPT
        
        Args:
            transcript: The user's speech transcript
            is_final: Whether this is a final transcript (vs interim)
            
        Returns:
            Decision enum indicating how to handle the transcript
        """
        # Priority 1: Empty edge case
        normalized = self._normalize(transcript)
        if not normalized:
            logger.debug(f"IGNORE (empty): '{transcript}'")
            return Decision.IGNORE
        
        # Priority 2: Agent not speaking (and outside grace period)
        # Fix #3: Use grace period check instead of direct state
        if not self._is_effectively_speaking():
            logger.debug(f"NO_DECISION (agent silent): '{transcript}'")
            return Decision.NO_DECISION
        
        # Priority 3: Check for interrupt commands (highest priority while speaking)
        if self._contains_interrupt_word(normalized):
            log_level = logging.INFO if is_final else logging.DEBUG
            logger.log(log_level, f"🛑 INTERRUPT (command, {'final' if is_final else 'interim'}): '{transcript}'")
            return Decision.INTERRUPT
        
        # Priority 4: Check if only filler/backchannel words
        if self._is_only_ignore_words(normalized):
            log_level = logging.INFO if is_final else logging.DEBUG
            logger.log(log_level, f"🔇 IGNORE ({'final' if is_final else 'interim'}): '{transcript}'")
            return Decision.IGNORE
        
        # Priority 5: Substantive content - user wants to speak
        log_level = logging.INFO if is_final else logging.DEBUG
        logger.log(log_level, f"🛑 INTERRUPT (substantive, {'final' if is_final else 'interim'}): '{transcript}'")
        return Decision.INTERRUPT
    
    def _normalize(self, text: str) -> str:
        """
        Normalize text for comparison.
        
        Fix #1: Handles hyphenated words like "uh-huh" → "uh huh"
        
        Transformations:
            - "Uh-huh!" → "uh huh"
            - "mm-hmm" → "mm hmm"
            - "Yeah!!" → "yeah"
            - "  ok  " → "ok"
        
        Args:
            text: Raw transcript text
            
        Returns:
            Normalized text ready for word matching
        """
        # Lowercase
        text = text.lower()
        
        # Fix #1: Convert hyphens to spaces BEFORE removing punctuation
        # This ensures "uh-huh" → "uh huh" (matches IGNORE_WORDS)
        text = text.replace('-', ' ')
        
        # Remove remaining punctuation (keep alphanumeric and spaces)
        text = re.sub(r"[^\w\s]", "", text)
        
        # Collapse multiple spaces and trim
        text = " ".join(text.split())
        
        return text
    
    def _contains_interrupt_word(self, normalized_text: str) -> bool:
        """
        Check if text contains any interrupt command words.
        
        Handles both single words and multi-word phrases like "hold on".
        
        Args:
            normalized_text: Already normalized text
            
        Returns:
            True if any interrupt word/phrase is found
        """
        # Check for multi-word phrases first (e.g., "hold on", "never mind")
        for phrase in self._interrupt_words:
            if " " in phrase and phrase in normalized_text:
                logger.debug(f"Matched interrupt phrase: '{phrase}'")
                return True
        
        # Check individual words using O(1) set intersection
        words = set(normalized_text.split())
        matched = words & self._interrupt_words
        if matched:
            logger.debug(f"Matched interrupt word(s): {matched}")
            return True
        
        return False
    
    def _is_only_ignore_words(self, normalized_text: str) -> bool:
        """
        Check if text contains ONLY ignore/filler words.
        
        Fix #2: Handles multi-word phrases like "i see", "got it"
        
        Args:
            normalized_text: Already normalized text
            
        Returns:
            True if all words are backchannel/filler words
        """
        if not normalized_text:
            return True
        
        # Fix #2: Step 1 - Check if entire text is a multi-word phrase
        if normalized_text in self._ignore_words:
            logger.debug(f"Matched full phrase: '{normalized_text}'")
            return True
        
        # Fix #2: Step 2 - Check word-by-word
        words = normalized_text.split()
        
        for word in words:
            if word not in self._ignore_words:
                # Check if this word is part of a known multi-word phrase
                found_in_phrase = False
                for phrase in self._ignore_words:
                    if " " in phrase and word in phrase.split():
                        # Verify the full phrase is in the text
                        if phrase in normalized_text:
                            found_in_phrase = True
                            break
                
                if not found_in_phrase:
                    return False
        
        return True
