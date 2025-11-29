from __future__ import annotations
from datetime import datetime


class TranscriptBuffer:
    """Stores recent transcripts to prevent duplicate processing."""

    def __init__(self, max_entries: int, duplicate_window_seconds: float):
        """Initialize buffer with size limit and duplicate time window."""
        self._buffer: dict[str, float] = {}
        self._max_entries = max_entries
        self._duplicate_window_seconds = duplicate_window_seconds

    def contains_recent(self, text: str) -> bool:
        """Return True if the text was seen within the recent time window."""
        now = datetime.now().timestamp()
        t = self._buffer.get(text)
        return t is not None and (now - t) < self._duplicate_window_seconds

    def add_entry(self, text: str) -> None:
        """Add a transcript entry and evict oldest if buffer exceeds capacity."""
        now = datetime.now().timestamp()
        self._buffer[text] = now

        while len(self._buffer) > self._max_entries:
            oldest_key = min(self._buffer.keys(), key=lambda k: self._buffer[k])
            del self._buffer[oldest_key]
