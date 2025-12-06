# interrupt_handler.py

import os
import re
from typing import Set


class IntelligentInterruptionHandler:
    """
    A policy handler to decide whether a user interruption should be processed or ignored.

    This is useful for preventing the agent from stuttering or pausing when the user
    provides natural backchannel feedback (e.g., "yeah", "ok", "hmm").

    The policy is as follows:

    1.  **If the agent is NOT speaking:**
        - Never ignore interruptions. All user input is processed.

    2.  **If the agent IS speaking:**
        - **Ignore** interruptions that only contain backchannel words (e.g., "yeah", "ok").
        - **Allow** interruptions that contain hard commands (e.g., "stop", "wait").
        - **Allow** interruptions that are full sentences or mixed content.
    """

    def __init__(
        self,
        ignore_words: list[str] | None = None,
        command_words: list[str] | None = None,
    ) -> None:
        # A set of backchannel/filler words to ignore during an interruption.
        if ignore_words is None:
            ignore_str = os.getenv(
                "INTERRUPTION_IGNORE_WORDS",
                "yeah,ok,okay,yep,yes,hmm,um,uh,mm-hmm,mm hmm,"
                "uh-huh,uh huh,alright,right,sure,mhmm,mhm",
            )
            ignore_words = [
                w.strip().lower()
                for w in ignore_str.split(",")
                if w.strip()
            ]

        # A set of command words that should always interrupt the agent.
        if command_words is None:
            command_str = os.getenv(
                "INTERRUPTION_COMMAND_WORDS",
                "stop,wait,no,hold on,hold,stop it,"
                "wait a second,wait a minute,pause",
            )
            command_words = [
                w.strip().lower()
                for w in command_str.split(",")
                if w.strip()
            ]

        self._ignore_words: Set[str] = set(ignore_words)
        self._command_words: Set[str] = set(command_words)

        # Agent's speaking state, updated via `set_agent_speaking`.
        self._agent_is_speaking: bool = False

    def is_command(self, transcript: str) -> bool:
        """
        Check if the transcript contains a hard interruption command.
        """
        normalized = self._normalize_transcript(transcript)
        if not normalized:
            return False
        return self._contains_command_word(normalized)

    def set_agent_speaking(self, is_speaking: bool) -> None:
        """
        Update the agent's speaking state. This should be called from the
        `agent_state_changed` event listener.
        """
        self._agent_is_speaking = is_speaking

    def should_ignore_interruption(self, transcript: str) -> bool:
        """
        Decide if this interruption should be ignored.

        Returns:
          True  → ignore (do NOT interrupt agent)
          False → allow (let LiveKit interrupt)
        """
        # If the agent is not speaking, never ignore user input.
        if not self._agent_is_speaking:
            return False

        normalized = self._normalize_transcript(transcript)
        if not normalized:
            # Ignore empty or whitespace-only transcripts to prevent stutter.
            return True

        # If a command is detected, the interruption must be allowed.
        if self._contains_command_word(normalized):
            return False

        words = self._extract_words(normalized)
        if not words:
            return True

        # Ignore the interruption only if all words are backchannel fillers.
        all_ignored = all(w in self._ignore_words for w in words)
        return all_ignored

    def _normalize_transcript(self, transcript: str) -> str:
        if not transcript:
            return ""
        text = transcript.lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _extract_words(self, text: str) -> list[str]:
        if not text:
            return []
        return re.findall(r"\b[\w-]+\b", text.lower())

    def _contains_command_word(self, text: str) -> bool:
        """
        Check if the text contains any of the configured command words/phrases.
        Handles multi-word phrases like "hold on" using word boundaries.
        """
        t = text.lower()

        # Check longer phrases first so "hold on" wins over "hold"
        for cmd in sorted(self._command_words, key=len, reverse=True):
            # Build a regex like: r"\bwait a second\b" or r"\bstop\b"
            pattern = r"\b" + re.escape(cmd) + r"\b"
            if re.search(pattern, t):
                return True
        return False

    def get_ignore_words(self) -> Set[str]:
        return set(self._ignore_words)

    def get_command_words(self) -> Set[str]:
        return set(self._command_words)
