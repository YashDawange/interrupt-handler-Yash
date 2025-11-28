from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .events import AgentState


@dataclass
class InterruptionConfig:
    """Config for handling backchanneling vs actual interruptions."""
    ignore_words: Sequence[str] = (
        "yeah", "ok", "okay", "hmm", "uh-huh", "mhm", "right", 
        "aha", "gotcha", "sure", "yep", "yup", "mm-hmm"
    )
    case_sensitive: bool = False
    enabled: bool = True


class InterruptionHandler:
    """Decides whether user input should interrupt the agent or not.
    
    When agent is speaking and user says 'yeah', 'ok', etc., we treat it
    as acknowledgement rather than interruption. But if they say 'wait' or
    'stop', we actually interrupt.
    """
    
    def __init__(self, config: InterruptionConfig | None = None) -> None:
        self.config = config or InterruptionConfig()
        self._patterns = self._build_patterns()
    
    def _build_patterns(self) -> list[re.Pattern]:
        patterns = []
        for word in self.config.ignore_words:
            flags = 0 if self.config.case_sensitive else re.IGNORECASE
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', flags)
            patterns.append(pattern)
        return patterns
    
    def should_ignore_transcript(
        self, 
        transcript: str, 
        agent_state: AgentState
    ) -> bool:
        """Check if we should ignore this transcript based on what the agent is doing."""
        if not self.config.enabled:
            return False
        
        # If agent isn't speaking, don't ignore anything - user might be responding
        if agent_state != "speaking":
            return False
        
        text = transcript.strip()
        if not text:
            return False
        
        # Extract words from transcript
        words = re.findall(r'\b\w+\b', text)
        if not words:
            return False
        
        # Check how many words match our ignore list
        matched = set()
        for word in words:
            for pattern in self._patterns:
                if pattern.fullmatch(word):
                    matched.add(word.lower())
                    break
        
        # Only ignore if ALL words are in the ignore list
        # This way "yeah wait" won't be ignored because "wait" isn't in the list
        return len(matched) == len(set(w.lower() for w in words))
    
    def should_interrupt(
        self,
        transcript: str,
        agent_state: AgentState
    ) -> bool:
        """Should we interrupt the agent for this transcript?"""
        return not self.should_ignore_transcript(transcript, agent_state)
