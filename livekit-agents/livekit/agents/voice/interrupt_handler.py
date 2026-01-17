from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable


# ---------------- CONFIG ---------------- #

DEFAULT_IGNORE_WORDS = {
    w.strip()
    for w in os.getenv(
        "IGNORED_INTERRUPTS",
        "yeah,yes,ok,okay,hmm,uh,uh-huh,right,aha"
    ).split(",")
}

DEFAULT_INTERRUPT_WORDS = {
    "stop",
    "wait",
    "no",
    "hold on",
    "pause",
}


# ---------------- HELPERS ---------------- #

def normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


# ---------------- DATA ---------------- #

@dataclass
class InterruptionDecision:
    ignore: bool = False
    interrupt: bool = False
    respond: bool = False


# ---------------- HANDLER ---------------- #

class InterruptHandler:
    def __init__(
        self,
        *,
        ignore_words: Iterable[str] = DEFAULT_IGNORE_WORDS,
        interrupt_words: Iterable[str] = DEFAULT_INTERRUPT_WORDS,
    ) -> None:
        self.ignore_words = set(ignore_words)
        self.interrupt_words = set(interrupt_words)

        self.agent_is_speaking: bool = False
        self.pending_ignore: bool = False
        self.pending_vad_interrupt: bool = False  # ✅ Added initialization

    # ---------- STATE ---------- #

    def on_agent_speaking_start(self) -> None:
        self.agent_is_speaking = True
        # Reset flags when a new speech starts
        self.pending_ignore = False
        self.pending_vad_interrupt = False

    def on_agent_speaking_end(self) -> None:
        self.agent_is_speaking = False
        self.pending_ignore = False
        self.pending_vad_interrupt = False

    def on_vad_interruption(self) -> None:
        """
        ✅ FIX: This method was missing.
        Called when VAD detects speech while the agent is talking.
        """
        # We set pending_ignore to True to activate the "HARD BLOCK" in agent_activity.py.
        # This prevents the default VAD logic from killing the audio immediately.
        self.pending_ignore = True
        self.pending_vad_interrupt = True

    # ---------- LOGIC ---------- #

    def is_filler(self, text: str) -> bool:
        if not text:
            return False
        words = set(normalize(text).split())
        return bool(words) and words.issubset(self.ignore_words)

    def contains_interrupt_word(self, text: str) -> bool:
        words = set(normalize(text).split())
        return any(w in words for w in self.interrupt_words)

    def decide(self, transcript: str) -> InterruptionDecision:
        text = normalize(transcript)

        if not text:
            return InterruptionDecision(ignore=True)

        if self.agent_is_speaking:
            # If user said "Stop" or "Wait", interrupt immediately
            if self.contains_interrupt_word(text):
                return InterruptionDecision(interrupt=True)

            # If it's just "Yeah/Ok", tell the agent to keep ignoring
            if self.is_filler(text):
                return InterruptionDecision(ignore=True)

            # For any other unknown speech, assume it's a real interruption
            return InterruptionDecision(interrupt=True)

        return InterruptionDecision(respond=True)