from __future__ import annotations

import re
from typing import Sequence

from ..tokenize.basic import split_words


class BackchannelingFilter:
    """
    A context-aware filter that distinguishes between passive acknowledgements
    (backchanneling) and active interruptions based on agent state and transcript content.
    """

    def __init__(
        self,
        *,
        ignore_words: Sequence[str] | None = None,
        interruption_words: Sequence[str] | None = None,
    ) -> None:
        """
        Initialize the backchanneling filter.

        Args:
            ignore_words: List of words that should be ignored when agent is speaking.
                Default: ['yeah', 'ok', 'okay', 'hmm', 'right', 'uh-huh', 'uh huh', 'mhm', 'mm-hmm', 'yep', 'yup', 'sure', 'got it', 'i see', 'alright']
            interruption_words: List of words that should always trigger interruption.
                Default: ['wait', 'stop', 'no', 'hold on', 'hang on', 'pause', 'cancel']
        """
        # Default ignore words (backchanneling/filler words)
        default_ignore_words = [
            "yeah",
            "ok",
            "okay",
            "hmm",
            "right",
            "uh-huh",
            "uh huh",
            "mhm",
            "mm-hmm",
            "yep",
            "yup",
            "sure",
            "got it",
            "i see",
            "alright",
            "all right",
            "uh",
            "um",
            "ah",
            "aha",
            "mm",
            "huh",
        ]

        # Default interruption words (commands that should always interrupt)
        default_interruption_words = [
            "wait",
            "stop",
            "no",
            "hold on",
            "hang on",
            "pause",
            "cancel",
            "don't",
            "dont",
            "not",
            "never",
            "wrong",
            "incorrect",
            "false",
        ]

        self._ignore_words = set(
            word.lower().strip() for word in (ignore_words or default_ignore_words)
        )
        self._interruption_words = set(
            word.lower().strip() for word in (interruption_words or default_interruption_words)
        )

        # Create regex patterns for phrase matching (multi-word phrases)
        self._ignore_phrases = [
            re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
            for phrase in self._ignore_words
            if " " in phrase
        ]
        self._interruption_phrases = [
            re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
            for phrase in self._interruption_words
            if " " in phrase
        ]

    def should_ignore_interruption(
        self, transcript: str, agent_is_speaking: bool
    ) -> bool:
        """
        Determine if an interruption should be ignored based on transcript and agent state.

        Args:
            transcript: The user's transcribed text
            agent_is_speaking: Whether the agent is currently speaking

        Returns:
            True if the interruption should be ignored (agent should continue speaking),
            False if the interruption should be processed (agent should stop).
        """
        if not agent_is_speaking:
            # If agent is not speaking, never ignore - treat as normal input
            return False

        if not transcript or not transcript.strip():
            # Empty transcript - don't ignore (let VAD handle it)
            return False

        # Normalize transcript for matching
        transcript_lower = transcript.lower().strip()

        # First, check for interruption words/phrases (semantic interruption)
        # If any interruption word is found, always interrupt
        for phrase_pattern in self._interruption_phrases:
            if phrase_pattern.search(transcript_lower):
                return False  # Don't ignore - this is a real interruption

        # Check single-word interruption words
        words = split_words(transcript_lower, split_character=True)
        word_texts = [word[0].lower() for word in words]

        for word in word_texts:
            if word in self._interruption_words:
                return False  # Don't ignore - this is a real interruption

        # Check if transcript contains only ignore words/phrases
        # Remove ignore phrases first
        remaining_text = transcript_lower
        for phrase_pattern in self._ignore_phrases:
            remaining_text = phrase_pattern.sub("", remaining_text)

        # Split remaining text and check if all words are in ignore list
        remaining_words = split_words(remaining_text, split_character=True)
        remaining_word_texts = [word[0].lower().strip() for word in remaining_words if word[0].strip()]

        # If all remaining words are in ignore list, ignore the interruption
        if remaining_word_texts:
            all_ignored = all(
                word in self._ignore_words or not word for word in remaining_word_texts
            )
            if all_ignored:
                return True  # Ignore - only backchanneling words

        # If we have some words that aren't in ignore list, don't ignore
        # (unless they're all punctuation/whitespace)
        if remaining_word_texts:
            return False

        # If transcript is empty after removing ignore phrases, ignore it
        return True

    def is_only_backchanneling(self, transcript: str) -> bool:
        """
        Check if transcript contains only backchanneling words (no interruption words).

        Args:
            transcript: The user's transcribed text

        Returns:
            True if transcript contains only backchanneling words, False otherwise.
        """
        if not transcript or not transcript.strip():
            return False

        transcript_lower = transcript.lower().strip()

        # Check for interruption words first
        for phrase_pattern in self._interruption_phrases:
            if phrase_pattern.search(transcript_lower):
                return False

        words = split_words(transcript_lower, split_character=True)
        word_texts = [word[0].lower() for word in words]

        for word in word_texts:
            if word in self._interruption_words:
                return False

        # Remove ignore phrases
        remaining_text = transcript_lower
        for phrase_pattern in self._ignore_phrases:
            remaining_text = phrase_pattern.sub("", remaining_text)

        # Check remaining words
        remaining_words = split_words(remaining_text, split_character=True)
        remaining_word_texts = [word[0].lower().strip() for word in remaining_words if word[0].strip()]

        # If all words are ignored or empty, it's only backchanneling
        if not remaining_word_texts:
            return True

        return all(word in self._ignore_words or not word for word in remaining_word_texts)

