import re
import logging
from dataclasses import dataclass, field
from typing import Set

logger = logging.getLogger("interrupt-filter")


@dataclass
class InterruptionPolicy:
    # Backchannel / filler words (soft acknowledgements)
    ignored_fillers: Set[str] = field(default_factory=lambda: {
        "uh", "um", "umm", "hmm", "mm", "ah", "er",
        "okay", "ok", "yeah", "yep", "yes", "right",
        "uh-huh", "mm-hmm", "mhm", "hm"
    })

    # Explicit interruption commands
    command_keywords: Set[str] = field(default_factory=lambda: {
        "stop", "wait", "pause", "hold", "cancel",
        "no", "hold on", "enough"
    })


class InterruptionDecision:
    IGNORE = "ignore"
    INTERRUPT = "interrupt"
    REGISTER = "register"


class InterruptionFilter:
    def __init__(self, policy: InterruptionPolicy):
        self.policy = policy

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s']", " ", text)
        return re.sub(r"\s+", " ", text)

    def _tokens(self, text: str) -> Set[str]:
        return set(self._normalize(text).split())

    def is_fillers_only(self, text: str) -> bool:
        tokens = self._tokens(text)
        return bool(tokens) and tokens.issubset(self.policy.ignored_fillers)

    def contains_command(self, text: str) -> bool:
        norm = self._normalize(text)
        tokens = self._tokens(text)

        for cmd in self.policy.command_keywords:
            if " " in cmd and cmd in norm:
                return True
            if cmd in tokens:
                return True
        return False

    # IDENTICAL LOGIC TO PASTED SCRIPT
    def decide(self, *, text: str, agent_speaking: bool):
        if not agent_speaking:
            return InterruptionDecision.REGISTER

        if self.is_fillers_only(text):
            return InterruptionDecision.IGNORE

        if self.contains_command(text):
            return InterruptionDecision.INTERRUPT

        # mixed / non-filler speech while agent is speaking
        return InterruptionDecision.INTERRUPT
