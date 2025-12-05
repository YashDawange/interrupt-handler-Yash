"""
Backchanneling Filter for LiveKit Agent

This module implements context-aware filtering to distinguish between passive 
acknowledgments (backchanneling) and active interruptions based on whether 
the agent is currently speaking.
"""

from __future__ import annotations

import re
from typing import Optional, Set


class BackchannelingFilter:
    """
    Filters out passive acknowledgments (backchanneling) when the agent is actively 
    speaking, while allowing them to be processed normally when the agent is silent.
    """

    def __init__(
        self,
        ignore_words: Optional[Set[str]] = None,
        command_keywords: Optional[Set[str]] = None,
    ):
        """
        Initialize the backchanneling filter.

        Args:
            ignore_words: Set of words to ignore as interruptions when agent is speaking.
                         Defaults to common backchanneling words.
            command_keywords: Set of keywords that indicate a real command/interruption.
                            Defaults to common command words.
        """
        if ignore_words is None:
            ignore_words = {
                "yeah",
                "yup",
                "yep",
                "yes",
                "ok",
                "okay",
                "alright",
                "right",
                "uh-huh",
                "uh huh",
                "uhuh",
                "hmm",
                "hm",
                "mm",
                "mmhm",
                "mhm",
                "aha",
                "ah",
                "ooh",
                "oh",
                "cool",
                "sure",
                "i see",
                "i understand",
                "got it",
                "understood",
            }
        self.ignore_words = {word.lower() for word in ignore_words}

        if command_keywords is None:
            command_keywords = {
                "stop",
                "wait",
                "hold",
                "pause",
                "hang on",
                "hold on",
                "no",
                "nope",
                "not",
                "don't",
                "don't",
                "cant",
                "can't",
                "repeat",
                "again",
                "back",
                "slower",
                "faster",
                "louder",
                "quieter",
                "but",
                "however",
                "actually",
                "well",
                "look",
                "listen",
                "excuse me",
                "pardon me",
                "sorry",
                "what",
                "huh",
                "pardon",
            }
        self.command_keywords = {word.lower() for word in command_keywords}

    def is_backchanneling(self, text: str) -> bool:
        """
        Determine if the given text is a passive acknowledgment (backchanneling).

        Args:
            text: The transcribed user input.

        Returns:
            True if the text is a backchanneling utterance, False otherwise.
        """
        if not text:
            return False

        # Normalize the text
        normalized = text.lower().strip()

        # Remove extra spaces
        normalized = re.sub(r"\s+", " ", normalized)

        # Split into words
        words = normalized.split()

        if not words:
            return False

        # Check if all words are in the ignore list
        # Allow for some punctuation at the end
        cleaned_words = [re.sub(r"[.,!?;:'\"-]$", "", word) for word in words]
        cleaned_words = [w for w in cleaned_words if w]  # Remove empty strings

        if not cleaned_words:
            return False

        # All words must be in the ignore list
        return all(word in self.ignore_words for word in cleaned_words)

    def contains_command(self, text: str) -> bool:
        """
        Determine if the given text contains a command word that should trigger interruption.

        Args:
            text: The transcribed user input.

        Returns:
            True if the text contains a command keyword, False otherwise.
        """
        if not text:
            return False

        normalized = text.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)

        # Split into words
        words = normalized.split()

        # Check for command keywords
        cleaned_words = [re.sub(r"[.,!?;:'\"-]$", "", word) for word in words]

        return any(word in self.command_keywords for word in cleaned_words)

    def should_interrupt_agent(
        self, text: str, agent_is_speaking: bool
    ) -> bool:
        """
        Determine if the user input should interrupt the agent.

        This is the main logic:
        - If agent is speaking and text is just backchanneling, return False (ignore it)
        - If text contains a command, return True (always interrupt)
        - Otherwise, return True (normal interruption)

        Args:
            text: The transcribed user input.
            agent_is_speaking: Whether the agent is currently speaking.

        Returns:
            True if the agent should be interrupted, False if the input should be ignored.
        """
        if not text:
            return False

        # If text contains a command keyword, always interrupt
        if self.contains_command(text):
            return True

        # If agent is not speaking, allow normal interruption
        if not agent_is_speaking:
            return True

        # If agent is speaking and text is just backchanneling, ignore it
        if self.is_backchanneling(text):
            return False

        # If agent is speaking and text is not backchanneling, interrupt
        return True
