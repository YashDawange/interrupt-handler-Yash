import string
import time
from typing import List
from . import config


def normalize_text(text: str) -> str:
    if not text:
        return ""
    s = text.lower().strip()
    s = s.translate(str.maketrans("", "", string.punctuation))
    s = " ".join(s.split())
    return s


def extract_confidence(ev) -> float:
    try:
        if not getattr(ev, "alternatives", None):
            return 0.5
        alt0 = ev.alternatives[0]
        conf = getattr(alt0, "confidence", None)
        if conf is None:
            conf = getattr(alt0, "score", None)
        if conf is None:
            return 0.5
        return float(conf)
    except Exception:
        return 0.5


class SlidingWindowCounter:
    def __init__(self, window_s: float):
        self.window = window_s
        self.timestamps: List[float] = []

    def add(self, t: float):
        self.timestamps.append(t)
        cutoff = t - self.window
        self.timestamps = [ts for ts in self.timestamps if ts >= cutoff]

    def count(self, now: float) -> int:
        cutoff = now - self.window
        return len([ts for ts in self.timestamps if ts >= cutoff])


def contains_interrupt_keyword(normalized: str) -> bool:
    if not normalized:
        return False
    for phrase in config.INTERRUPT_KEYWORDS:
        if phrase in normalized:
            return True
    for p in config.PROFANITY_INTERRUPTS:
        if p in normalized:
            return True
    return False


def is_pure_backchannel(normalized: str) -> bool:
    if not normalized:
        return False

    # Direct phrase match (e.g., "yeah yeah", "i see", "sounds good")
    if normalized in config.IGNORE_PHRASES:
        return True

    toks = normalized.split()

    # NEW: treat repeated backchannel words as backchannel ("yeah yeah", "ok ok ok")
    if all(tok in config.IGNORE_WORDS for tok in toks):
        return True

    return False
