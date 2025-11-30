"""
Intelligent Interruption Filter

Distinguishes between:
- Backchanneling (passive): "yeah", "ok", "hmm"
- Commands (active): "stop", "wait", "no"
- Mixed: "yeah but wait" (has command → interrupt)
"""

import os
import re
from dataclasses import dataclass
from typing import Set, Optional


@dataclass
class InterruptionDecision:
    """Result of analyzing user input."""
    should_interrupt: bool
    reason: str
    is_backchanneling: bool


class InterruptionFilter:
    """
    Filters interruptions based on content and agent state.
    
    Configuration via environment:
        BACKCHANNEL_WORDS="yeah,ok,hmm,uh-huh"
    """
    
    DEFAULT_BACKCHANNEL_WORDS = {
        "yeah", "yep", "yes", "yah", "ya", "yup",
        "ok", "okay", "k", "kay",
        "hmm", "hm", "mm", "mmm", "mhm", "mhmm", "mmhmm",
        "uh-huh", "uh huh", "uhuh", "mm-hmm", "mm hmm",
        "right", "alright", "all right", "sure", "gotcha", "got it",
        "aha", "ah", "oh", "ooh", "wow",
        "go on", "go ahead", "continue", "i see",
    }
    
    def __init__(self, custom_words: Optional[Set[str]] = None):
        """Initialize with default + environment words."""
        if custom_words:
            self.backchannel_words = set(w.lower().strip() for w in custom_words)
        else:
            self.backchannel_words = self.DEFAULT_BACKCHANNEL_WORDS.copy()
            
            # Add from environment
            env_words = os.getenv("BACKCHANNEL_WORDS", "")
            if env_words:
                additional = {w.lower().strip() for w in env_words.split(",") if w.strip()}
                self.backchannel_words.update(additional)
    
    def normalize_text(self, text: str) -> str:
        """Lowercase and remove punctuation."""
        text = text.lower().strip()
        text = re.sub(r'[.,!?;:\'\"]', '', text)
        return text
    
    def is_pure_backchanneling(self, text: str) -> bool:
        """Check if text contains ONLY backchanneling words.

        This method matches known backchannel words but also attempts to
        recognize common non-lexical fillers that speech-to-text engines
        sometimes render in short, noisy forms (e.g. "mm", "mhmm", "hmm").

        An empty transcript is NOT treated as a backchannel here; instead we
        rely on a short-utterance VAD heuristic at the integration layer to
        handle cases where the STT returns an empty string for a hum.
        """
        if not text or not text.strip():
            return False

        normalized = self.normalize_text(text)
        
        # Check if entire phrase is known
        if normalized in self.backchannel_words:
            return True
        
        # Check if all words are backchanneling
        words = normalized.split()
        if not words:
            return False

        # If every token is in the known backchannel list, it's a backchannel.
        if all(word in self.backchannel_words for word in words):
            return True

        # Fuzzy match common non-lexical fillers that may not be normalized
        # into dictionary words by STT. Examples: "mm", "mhm", "mhmm", "hmm".
        filler_re = re.compile(r'^[mh]{1,6}$')
        if len(words) == 1 and filler_re.match(words[0]):
            return True

        # Also recognize repeated short hums like 'uh uh' or 'uhh'
        filler_re2 = re.compile(r'^(uh+|uhh+|uh-huh|uh huh|uhuh)$')
        if len(words) == 1 and filler_re2.match(words[0]):
            return True

        return False
    
    def should_allow_interruption(
        self,
        transcript: str,
        agent_is_speaking: bool,
        is_final: bool = False
    ) -> InterruptionDecision:
        """
        Main decision logic.
        
        Logic Matrix:
        | User Input  | Agent State | Action                    |
        |-------------|-------------|---------------------------|
        | "yeah"      | Speaking    | Don't interrupt (resume)  |
        | "stop"      | Speaking    | Interrupt immediately     |
        | "yeah"      | Silent      | Process as valid input    |
        | "yeah wait" | Speaking    | Interrupt (has command)   |
        """
        is_backchanneling = self.is_pure_backchanneling(transcript)
        
        if agent_is_speaking:
            if is_backchanneling:
                return InterruptionDecision(
                    should_interrupt=False,
                    reason=f"Backchanneling while speaking: '{transcript}'",
                    is_backchanneling=True
                )
            else:
                return InterruptionDecision(
                    should_interrupt=True,
                    reason=f"Command while speaking: '{transcript}'",
                    is_backchanneling=False
                )
        else:
            # Agent silent - always process input
            return InterruptionDecision(
                should_interrupt=True,
                reason=f"Agent silent, processing: '{transcript}'",
                is_backchanneling=is_backchanneling
            )