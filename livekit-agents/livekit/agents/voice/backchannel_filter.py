from __future__ import annotations

import re
from typing import Sequence

from ..tokenize.basic import split_words


# Default list of backchannel words/phrases that should be ignored when agent is speaking
DEFAULT_BACKCHANNEL_WORDS = {
    "yeah",
    "ok",
    "okay",
    "hmm",
    "uh-huh",
    "uh huh",
    "mhm",
    "mm-hmm",
    "mm hmm",
    "right",
    "sure",
    "yep",
    "yup",
    "mm",
    "ah",
    "oh",
    "uh",
    "um",
    "huh",
    "aha",
    "got it",
    "gotcha",
    "i see",
    "i see",
    "alright",
    "all right",
    "alrighty",
    "cool",
    "nice",
    "wow",
    "okay then",
    "sounds good",
}

# Default list of interruption commands that should always trigger interruption
DEFAULT_INTERRUPTION_COMMANDS = {
    "stop",
    "wait",
    "no",
    "hold on",
    "pause",
    "cancel",
    "halt",
    "cease",
    "enough",
    "quit",
    "end",
    "abort",
    "cut",
    "break",
}


class BackchannelFilter:
    """
    Filters backchannel acknowledgments from real interruption commands.

    This filter distinguishes between:
    - Backchannel words (e.g., "yeah", "ok", "hmm") that should be ignored when agent is speaking
    - Real interruption commands (e.g., "stop", "wait", "no") that must interrupt the agent
    - Mixed phrases (e.g., "yeah but wait") that contain real intent and should interrupt

    The filter only applies when the agent is currently speaking. When the agent is silent,
    all user input (including backchannels) is treated as valid input.
    """

    def __init__(
        self,
        backchannel_words: Sequence[str] | None = None,
        interruption_commands: Sequence[str] | None = None,
    ) -> None:
        """
        Initialize the backchannel filter.

        Args:
            backchannel_words: List of words/phrases to treat as backchannels.
                If None, uses DEFAULT_BACKCHANNEL_WORDS.
            interruption_commands: List of words/phrases that always trigger interruption.
                If None, uses DEFAULT_INTERRUPTION_COMMANDS.
        """
        # Normalize backchannel words to lowercase and create a set for O(1) lookup
        if backchannel_words is None:
            self._backchannel_set = {word.lower() for word in DEFAULT_BACKCHANNEL_WORDS}
        else:
            self._backchannel_set = {word.lower().strip() for word in backchannel_words}

        # Normalize interruption commands to lowercase and create a set for O(1) lookup
        if interruption_commands is None:
            self._interruption_set = {word.lower() for word in DEFAULT_INTERRUPTION_COMMANDS}
        else:
            self._interruption_set = {word.lower().strip() for word in interruption_commands}

        # Pre-compile regex for punctuation removal
        self._punctuation_regex = re.compile(r"[^\w\s]")

    def _normalize_text(self, text: str) -> str:
        """Normalize text by lowercasing and removing extra whitespace."""
        if not text:
            return ""
        # Remove punctuation and normalize whitespace
        text = self._punctuation_regex.sub(" ", text)
        text = " ".join(text.split())  # Normalize whitespace
        return text.lower().strip()

    def _contains_interruption_command(self, text: str) -> bool:
        """
        Check if text contains any interruption command.

        Args:
            text: The text to check.

        Returns:
            True if text contains an interruption command, False otherwise.
        """
        normalized = self._normalize_text(text)
        if not normalized:
            return False

        # Check for exact phrase matches first (longer phrases)
        for cmd in sorted(self._interruption_set, key=len, reverse=True):
            if cmd in normalized:
                return True

        return False

    def _is_backchannel_only(self, text: str) -> bool:
        """
        Check if text contains only backchannel words.

        Args:
            text: The text to check.

        Returns:
            True if text contains only backchannels, False if it contains other words.
        """
        normalized = self._normalize_text(text)
        if not normalized:
            return True  # Empty text is treated as backchannel (ignore)

        # First check if the entire normalized text matches a backchannel phrase exactly
        if normalized in self._backchannel_set:
            return True

        # Try to match multi-word backchannels first (longer phrases first)
        # This handles cases like "got it", "i see" as complete phrases
        remaining_text = normalized
        sorted_backchannels = sorted(self._backchannel_set, key=len, reverse=True)
        
        for backchannel in sorted_backchannels:
            # Use word boundary matching to avoid partial matches
            # e.g., "got" shouldn't match "forgot"
            pattern = r'\b' + re.escape(backchannel) + r'\b'
            if re.search(pattern, remaining_text):
                # Replace the matched backchannel with spaces
                remaining_text = re.sub(pattern, ' ', remaining_text)
                remaining_text = ' '.join(remaining_text.split())  # Normalize whitespace

        # After removing all multi-word backchannels, check remaining words
        remaining_words = [w.strip() for w in remaining_text.split() if w.strip()]
        
        # All remaining words must be single-word backchannels
        for word in remaining_words:
            if word not in self._backchannel_set:
                # This word is not a backchannel
                return False

        # If we've matched all words/phrases as backchannels, return True
        return True

    def should_ignore_interruption(
        self, text: str, agent_is_speaking: bool
    ) -> bool:
        """
        Determine if an interruption should be ignored based on the transcript.

        Args:
            text: The user's transcribed text.
            agent_is_speaking: Whether the agent is currently speaking.

        Returns:
            True if the interruption should be ignored (i.e., it's only backchannels),
            False if the interruption should proceed (i.e., it contains real intent).
        """
        # If agent is not speaking, never ignore interruptions
        # All user input is valid when agent is silent
        if not agent_is_speaking:
            return False

        # Normalize the text
        normalized = self._normalize_text(text)
        if not normalized:
            return True  # Empty text should be ignored

        # First check for interruption commands - these always interrupt
        if self._contains_interruption_command(normalized):
            return False

        # Check if text contains only backchannels
        if self._is_backchannel_only(normalized):
            return True

        # If we get here, the text contains non-backchannel words
        # that are not explicit interruption commands, but still represent real intent
        return False

