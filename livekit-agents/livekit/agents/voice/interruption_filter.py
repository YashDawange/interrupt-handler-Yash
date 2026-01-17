from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class InterruptionDecision:
    should_interrupt: bool
    reason: Literal["backchannel_ignored", "command_detected", "valid_input", "agent_silent"]
    transcript: str


class InterruptionFilter:
    DEFAULT_BACKCHANNEL_WORDS: frozenset[str] = frozenset([
        "yeah", "yes", "yep", "yup", "uh-huh", "uh huh", "uhuh",
        "ok", "okay", "k", "mm-hmm", "mmhmm", "mm hmm", "mhm",
        "hmm", "hm", "right", "sure", "got it", "gotcha",
        "aha", "ah", "oh", "i see", "alright", "all right"
    ])

    DEFAULT_INTERRUPT_COMMANDS: frozenset[str] = frozenset([
        "wait", "stop", "hold on", "hold up", "pause", "no",
        "actually", "but", "however", "hang on", "one second",
        "excuse me", "sorry", "question"
    ])

    def __init__(
        self,
        backchannel_words: frozenset[str] | None = None,
        interrupt_commands: frozenset[str] | None = None,
    ) -> None:
        self._backchannel_words = backchannel_words or self.DEFAULT_BACKCHANNEL_WORDS
        self._interrupt_commands = interrupt_commands or self.DEFAULT_INTERRUPT_COMMANDS

    @property
    def backchannel_words(self) -> frozenset[str]:
        return self._backchannel_words

    @property
    def interrupt_commands(self) -> frozenset[str]:
        return self._interrupt_commands

    def is_pure_backchannel(self, transcript: str) -> bool:
        normalized = transcript.lower().strip()
        if not normalized:
            return True

        if normalized in self._backchannel_words:
            return True

        for bc in self._backchannel_words:
            if normalized == bc or normalized.replace(",", "").replace(".", "").strip() == bc:
                return True

        words = re.findall(r'\b\w+\b', normalized)
        if not words:
            return True

        return all(word in self._backchannel_words for word in words)

    def contains_interrupt_command(self, transcript: str) -> bool:
        normalized = transcript.lower().strip()
        for cmd in self._interrupt_commands:
            if cmd in normalized:
                return True
        return False

    def should_interrupt(
        self,
        transcript: str,
        agent_is_speaking: bool
    ) -> InterruptionDecision:
        if not agent_is_speaking:
            return InterruptionDecision(
                should_interrupt=True,
                reason="agent_silent",
                transcript=transcript
            )

        if self.contains_interrupt_command(transcript):
            return InterruptionDecision(
                should_interrupt=True,
                reason="command_detected",
                transcript=transcript
            )

        if self.is_pure_backchannel(transcript):
            return InterruptionDecision(
                should_interrupt=False,
                reason="backchannel_ignored",
                transcript=transcript
            )

        return InterruptionDecision(
            should_interrupt=True,
            reason="valid_input",
            transcript=transcript
        )
