"""
Intelligent Interruption Filter for LiveKit Agents

This module implements context-aware filtering of user speech to distinguish between
passive acknowledgements (backchanneling) and active interruptions based on the agent's
speaking state.

The filter prevents the agent from stopping when users say filler words like "yeah", "ok",
or "hmm" while the agent is actively speaking, while still allowing these same words to
be processed as valid input when the agent is silent.

Author: VANKUDOTHU RAJESHWAR
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class InterruptionDecision:
    """Result of interruption filtering decision"""

    should_interrupt: bool
    """Whether the agent should be interrupted"""

    reason: str
    """Human-readable reason for the decision"""

    matched_words: list[str]
    """Words from ignore/command lists that were matched"""


class InterruptionFilter:
    """
    Context-aware filter that determines whether user speech should interrupt the agent.

    The filter operates on the following logic:
    - When agent is SPEAKING:
        * Ignore filler words (yeah, ok, hmm, etc.) → NO interruption
        * Recognize command words (wait, stop, no, etc.) → YES interruption
        * Mixed input (contains both) → YES interruption (command takes precedence)
    - When agent is SILENT:
        * Process all input normally → Allow processing as valid user input

    Configuration via environment variables:
    - INTERRUPT_IGNORE_LIST: Comma-separated list of words to ignore while speaking
                            (default: "yeah,ok,okay,hmm,uh-huh,mm-hmm,right,aha")
    - INTERRUPT_COMMAND_LIST: Comma-separated list of explicit command words
                             (default: "wait,stop,no,hold,pause,but")
    """

    DEFAULT_IGNORE_LIST = [
        "yeah",
        "ok",
        "okay",
        "hmm",
        "uh-huh",
        "mm-hmm",
        "right",
        "aha",
        "mhm",
        "mm",
        "uh",
        "um",
        "huh",  # Part of "uh-huh"
    ]

    DEFAULT_COMMAND_LIST = [
        "wait",
        "stop",
        "no",
        "hold",
        "pause",
        "but",
        "actually",
        "however",
    ]

    def __init__(
        self,
        ignore_list: list[str] | None = None,
        command_list: list[str] | None = None,
    ) -> None:
        """
        Initialize the interruption filter.

        Args:
            ignore_list: List of words to ignore when agent is speaking.
                        If None, loads from INTERRUPT_IGNORE_LIST env var or uses defaults.
            command_list: List of words that always trigger interruption.
                         If None, loads from INTERRUPT_COMMAND_LIST env var or uses defaults.
        """
        # Load ignore list from environment or use provided/default
        if ignore_list is None:
            env_ignore = os.getenv("INTERRUPT_IGNORE_LIST")
            if env_ignore:
                ignore_list = [w.strip().lower() for w in env_ignore.split(",")]
            else:
                ignore_list = self.DEFAULT_IGNORE_LIST.copy()
        else:
            ignore_list = [w.lower() for w in ignore_list]

        # Load command list from environment or use provided/default
        if command_list is None:
            env_command = os.getenv("INTERRUPT_COMMAND_LIST")
            if env_command:
                command_list = [w.strip().lower() for w in env_command.split(",")]
            else:
                command_list = self.DEFAULT_COMMAND_LIST.copy()
        else:
            command_list = [w.lower() for w in command_list]

        self._ignore_set = set(ignore_list)
        self._command_set = set(command_list)

        logger.info(
            "InterruptionFilter initialized",
            extra={
                "ignore_words": sorted(self._ignore_set),
                "command_words": sorted(self._command_set),
            },
        )

    def should_interrupt(
        self,
        transcript: str,
        agent_state: Literal["speaking", "listening", "thinking"],
    ) -> InterruptionDecision:
        """
        Determine if user speech should interrupt the agent based on context.

        Args:
            transcript: User's spoken text (from STT interim or final transcript)
            agent_state: Current state of the agent

        Returns:
            InterruptionDecision with the verdict and reasoning
        """
        # Normalize and tokenize the transcript
        normalized = transcript.lower().strip()

        if not normalized:
            return InterruptionDecision(
                should_interrupt=False, reason="Empty transcript", matched_words=[]
            )

        # When agent is not speaking, always allow processing
        # (user input should be processed normally)
        if agent_state != "speaking":
            return InterruptionDecision(
                should_interrupt=True,
                reason=f"Agent is {agent_state}, processing user input normally",
                matched_words=[],
            )

        # Agent is speaking - apply intelligent filtering
        words = self._tokenize(normalized)

        # Check for command words first (highest priority)
        command_matches = [w for w in words if w in self._command_set]
        if command_matches:
            return InterruptionDecision(
                should_interrupt=True,
                reason="Command word detected while agent speaking",
                matched_words=command_matches,
            )

        # Check if ALL words are in the ignore list
        ignore_matches = [w for w in words if w in self._ignore_set]
        non_ignore_words = [w for w in words if w not in self._ignore_set]

        if non_ignore_words:
            # Contains words that are NOT in the ignore list → interrupt
            return InterruptionDecision(
                should_interrupt=True,
                reason="Non-filler content detected while agent speaking",
                matched_words=non_ignore_words,
            )

        # All words are filler/backchanneling → do NOT interrupt
        return InterruptionDecision(
            should_interrupt=False,
            reason="Only filler words detected while agent speaking",
            matched_words=ignore_matches,
        )

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text into words, removing punctuation and splitting properly.

        Args:
            text: Input text

        Returns:
            List of normalized words
        """
        # Remove punctuation and split into words
        text = re.sub(r"[^\w\s-]", " ", text)
        words = text.split()

        # Further split hyphenated words if needed
        result = []
        for word in words:
            if "-" in word:
                # Handle compounds like "uh-huh" and "mm-hmm"
                result.append(word)  # Keep the full hyphenated version
                # Also add the parts separately
                parts = word.split("-")
                result.extend(parts)
            else:
                result.append(word)

        return [w.strip() for w in result if w.strip()]
