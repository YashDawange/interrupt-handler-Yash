from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable


def _parse_csv_env(name: str, default: Iterable[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return [w.strip().lower() for w in default]
    return [w.strip().lower() for w in raw.split(",") if w.strip()]


DEFAULT_SOFT_ACKS: list[str] = [
    "yeah",
    "yep",
    "ok",
    "okay",
    "hmm",
    "uh-huh",
    "uhhuh",
    "uh",
    "huh",
    "mm-hmm",
    "mmhmm",
    "mhm",
    "mhmm",
    "mm",
    "mmm",
    "right",
    "aha",
]

DEFAULT_HARD_INTERRUPTS: list[str] = [
    "stop",
    "wait",
    "no",
    "cancel",
    "hold on",
    "pause",
]


@dataclass
class InterruptionPolicy:
    soft_words: set[str]
    hard_words: set[str]
    hard_re: re.Pattern[str]
    ack_grace_ms: int

    @classmethod
    def from_env(cls) -> "InterruptionPolicy":
        soft = set(_parse_csv_env("LIVEKIT_SOFT_ACKS", DEFAULT_SOFT_ACKS))
        hard = set(_parse_csv_env("LIVEKIT_HARD_INTERRUPTS", DEFAULT_HARD_INTERRUPTS))
        escaped = [re.escape(w) for w in sorted(hard, key=len, reverse=True)]
        hard_re = re.compile(r"(?:^|[^A-Za-z0-9_])(" + "|".join(escaped) + r")(?:$|[^A-Za-z0-9_])", re.I)
        ack_grace_ms = int(os.getenv("LIVEKIT_ACK_GRACE_MS", "180"))
        return cls(soft_words=soft, hard_words=hard, hard_re=hard_re, ack_grace_ms=ack_grace_ms)

    def contains_hard(self, text: str) -> bool:
        if not text:
            return False
        return bool(self.hard_re.search(text))

    def is_only_soft_ack(self, text: str) -> bool:
        if not text:
            return True
        normalized = re.sub(r"[^\w\s]", " ", text.lower()).strip()
        if not normalized:
            return True
        words = [w for w in normalized.split() if w]
        if not words:
            return True
        return all(w in self.soft_words for w in words)



