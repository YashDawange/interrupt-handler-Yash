# Copyright 2025 LiveKit, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Intelligent Interruption Handler for LiveKit Agents

This module provides context-aware interruption handling that distinguishes between
passive acknowledgements (backchanneling) and active interruptions based on agent state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .events import AgentState


@dataclass
class InterruptionConfig:
    """Configuration for intelligent interruption handling.
    
    Attributes:
        ignore_words: List of words that should be ignored when agent is speaking.
            These are typically backchanneling words like "yeah", "ok", "hmm", etc.
        case_sensitive: Whether word matching should be case-sensitive.
        enabled: Whether the intelligent interruption handler is enabled.
    """
    ignore_words: Sequence[str] = (
        "yeah", "ok", "okay", "hmm", "uh-huh", "mhm", "right", 
        "aha", "gotcha", "sure", "yep", "yup", "mm-hmm"
    )
    case_sensitive: bool = False
    enabled: bool = True


class InterruptionHandler:
    """Handles context-aware interruption filtering.
    
    This handler implements the logic matrix:
    - User says "yeah/ok/hmm" while agent is speaking -> IGNORE
    - User says "wait/stop/no" while agent is speaking -> INTERRUPT
    - User says "yeah/ok/hmm" while agent is silent -> RESPOND
    - User says anything while agent is silent -> RESPOND
    """
    
    def __init__(self, config: InterruptionConfig | None = None) -> None:
        """Initialize the interruption handler.
        
        Args:
            config: Configuration for the handler. If None, uses default config.
        """
        self.config = config or InterruptionConfig()
        
        # Compile regex patterns for efficient matching
        self._ignore_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> list[re.Pattern]:
        """Compile regex patterns for ignore words.
        
        Returns:
            List of compiled regex patterns.
        """
        patterns = []
        for word in self.config.ignore_words:
            # Create pattern that matches the word as a standalone word
            # This ensures "yeah" matches "yeah" but not "year"
            flags = 0 if self.config.case_sensitive else re.IGNORECASE
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', flags)
            patterns.append(pattern)
        return patterns
    
    def should_ignore_transcript(
        self, 
        transcript: str, 
        agent_state: AgentState
    ) -> bool:
        """Determine if a transcript should be ignored based on agent state.
        
        Args:
            transcript: The transcript text to evaluate.
            agent_state: Current state of the agent ("speaking", "listening", "thinking").
        
        Returns:
            True if the transcript should be ignored, False otherwise.
        
        Logic:
            - If handler is disabled, never ignore
            - If agent is NOT speaking, never ignore (always respond)
            - If agent IS speaking:
                - Check if transcript contains ONLY ignore words -> ignore
                - Check if transcript contains ANY non-ignore words -> don't ignore
        """
        if not self.config.enabled:
            return False
        
        # Never ignore when agent is not speaking
        # This allows "yeah" to be a valid response when agent is silent
        if agent_state != "speaking":
            return False
        
        # Clean the transcript
        text = transcript.strip()
        if not text:
            return False
        
        # Check if the entire transcript consists only of ignore words
        # We need to determine if there are any "command" words that should interrupt
        
        # Split into words and check each
        words = re.findall(r'\b\w+\b', text)
        if not words:
            return False
        
        # Track which words match ignore patterns
        matched_words = set()
        for word in words:
            for pattern in self._ignore_patterns:
                if pattern.fullmatch(word):
                    matched_words.add(word.lower())
                    break
        
        # If ALL words are ignore words, then ignore the transcript
        # If ANY word is NOT an ignore word, don't ignore (it's a real command)
        all_words_match = len(matched_words) == len(set(w.lower() for w in words))
        
        return all_words_match
    
    def should_interrupt(
        self,
        transcript: str,
        agent_state: AgentState
    ) -> bool:
        """Determine if a transcript should trigger an interruption.
        
        This is the inverse of should_ignore_transcript with additional clarity.
        
        Args:
            transcript: The transcript text to evaluate.
            agent_state: Current state of the agent.
        
        Returns:
            True if the agent should be interrupted, False otherwise.
        """
        return not self.should_ignore_transcript(transcript, agent_state)
