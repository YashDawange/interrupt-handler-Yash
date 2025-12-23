from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Literal


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for lightweight matching."""
    return re.sub(r"[^a-z\s]", " ", text.lower()).strip()


def _split_words(text: str) -> list[str]:
    return [part for part in text.split() if part]


class SoftWordFilter:
    def __init__(self, soft_words: Iterable[str]) -> None:
        # Store both phrase-level and token-level representations.
        #
        # Why both?
        # - Some backchannels are multi-word phrases ("uh huh", "mm hmm", "got it").
        # - Some fillers should be treated as soft even when they appear alone ("uh").
        self._soft_phrases = {_normalize(w) for w in soft_words if _normalize(w)}
        self._soft_phrase_tokens: list[list[str]] = sorted(
            (_split_words(p) for p in self._soft_phrases if _split_words(p)),
            key=len,
            reverse=True,
        )

        # Common filler tokens; used to treat phrase components like "uh" in "uh huh"
        # as soft even when they appear alone.
        filler_tokens = {
            "uh",
            "um",
            "mm",
            "mhm",
            "hmm",
            "huh",
            "aha",
            "yeah",
            "yep",
            "ok",
            "okay",
            "right",
            "sure",
            "yes",
        }

        self._soft_tokens: set[str] = set()
        for phrase in self._soft_phrase_tokens:
            if len(phrase) == 1:
                self._soft_tokens.add(phrase[0])
            else:
                # Only promote clearly-filler parts of multi-word phrases to token-level soft.
                for token in phrase:
                    if token in filler_tokens:
                        self._soft_tokens.add(token)

    def is_soft_only(self, text: str) -> bool:
        normalized = _normalize(text)
        if not normalized:
            return False

        tokens = _split_words(normalized)
        return bool(tokens) and self._can_segment_all_soft(tokens)

    def strip_soft_words(self, text: str) -> str:
        normalized = _normalize(text)

        tokens = _split_words(normalized)
        remaining: list[str] = []

        i = 0
        while i < len(tokens):
            phrase_len = self._match_soft_phrase(tokens, i)
            if phrase_len:
                i += phrase_len
                continue

            token = tokens[i]
            if token in self._soft_tokens:
                i += 1
                continue

            remaining.append(token)
            i += 1

        return " ".join(remaining)

    def _match_soft_phrase(self, tokens: list[str], start_idx: int) -> int:
        for phrase in self._soft_phrase_tokens:
            end_idx = start_idx + len(phrase)
            if end_idx <= len(tokens) and tokens[start_idx:end_idx] == phrase:
                return len(phrase)
        return 0

    def _can_segment_all_soft(self, tokens: list[str]) -> bool:
        i = 0
        while i < len(tokens):
            phrase_len = self._match_soft_phrase(tokens, i)
            if phrase_len:
                i += phrase_len
                continue

            if tokens[i] in self._soft_tokens:
                i += 1
                continue

            return False

        return True


class CommandDetector:
    """Classifies short user utterances into soft / command / content buckets.

    Intended for semantic interruption handling:
    - soft: backchanneling/fillers ("yeah", "ok", "uh-huh")
    - stop: hard interruption commands ("stop", "wait")
    - correction: user is correcting the agent mid-speech
    - content: anything else
    """

    def __init__(
        self,
        *,
        stop_commands: Sequence[str],
        correction_cues: Sequence[str],
        soft_filter: SoftWordFilter,
    ) -> None:
        self._stop_commands = [_normalize(cmd) for cmd in stop_commands if _normalize(cmd)]
        self._correction_cues = [_normalize(cmd) for cmd in correction_cues if _normalize(cmd)]
        self._soft_filter = soft_filter

    def classify(self, text: str) -> tuple[Literal["soft", "stop", "correction", "content", "empty"], str]:  # noqa: E501
        normalized = _normalize(text)
        if not normalized:
            return "empty", ""

        if self._contains_phrase(normalized, self._stop_commands):
            cleaned = self._soft_filter.strip_soft_words(text)
            return "stop", cleaned or normalized

        if self._contains_phrase(normalized, self._correction_cues):
            cleaned = self._soft_filter.strip_soft_words(text)
            return "correction", cleaned or normalized

        if self._soft_filter.is_soft_only(text):
            return "soft", ""

        cleaned = self._soft_filter.strip_soft_words(text)
        return "content", cleaned or normalized

    def _contains_phrase(self, text: str, phrases: Sequence[str]) -> bool:
        return any(f" {phrase} " in f" {text} " for phrase in phrases if phrase)
