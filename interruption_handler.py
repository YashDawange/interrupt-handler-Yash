import logging
import re
from enum import Enum
from typing import Iterable, Tuple

import config
from state_manager import AgentStateTracker

logger = logging.getLogger(__name__)


_WORD_RE = re.compile(r"[\w-]+", flags=re.UNICODE)


class Decision(Enum):
    """High-level decision about how to treat a user utterance."""

    IGNORE = "ignore"
    INTERRUPT = "interrupt"
    RESPOND = "respond"


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase word-like tokens, stripping punctuation.

    This is more robust than a simple str.split(), especially around
    punctuation and non-ASCII characters.
    """

    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


def _contains_any(words: Iterable[str], vocab: Iterable[str]) -> bool:
    vocab_set = set(vocab)
    return any(w in vocab_set for w in words)


class InterruptionHandler:
    """Pure decision engine for interruption handling.

    Given the current STT transcript and agent speaking state, it decides
    whether to ignore the input, interrupt the agent, or treat the input
    as a normal user message that should be responded to.
    """

    def __init__(self, state_tracker: AgentStateTracker) -> None:
        self._state_tracker = state_tracker

    def analyze_input(self, text: str, agent_state_when_queued: str) -> Tuple[Decision, str]:
        """Analyze a user utterance and return (Decision, reason).

        The logic is:
        - Empty / whitespace-only input -> IGNORE
        - Normalize and tokenize text
        - If agent is speaking:
            * If utterance has an interrupt word -> INTERRUPT
            * Else if utterance is a short pure backchannel -> IGNORE
            * Else -> INTERRUPT (mixed or longer content)
        - If agent is silent:
            * RESPOND (treat as valid input)
        """

        if not text or not text.strip():
            logger.debug("InterruptionHandler: ignoring empty input")
            return (Decision.IGNORE, "empty input")

        tokens = _tokenize(text)

        if not tokens:
            logger.debug("InterruptionHandler: ignoring non-tokenizable input: %r", text)
            return (Decision.IGNORE, "no tokens after normalization")

        agent_speaking = agent_state_when_queued == "speaking"

        has_interrupt_word = _contains_any(tokens, config.INTERRUPT_WORDS)

        is_pure_backchannel = (
            len(tokens) <= 4
            and all(t in config.BACKCHANNEL_WORDS for t in tokens)
        )

        if agent_speaking:
            if has_interrupt_word:
                reason = f"interrupt word detected while speaking: {text!r}"
                logger.info("Decision.INTERRUPT: %s", reason)
                return (Decision.INTERRUPT, reason)

            if is_pure_backchannel:
                reason = f"backchannel while speaking: {text!r}"
                logger.info("Decision.IGNORE: %s", reason)
                return (Decision.IGNORE, reason)

            # Mixed phrase or longer content such as "yeah but wait", or
            # multi-word sentences not entirely in BACKCHANNEL_WORDS.
            reason = f"non-backchannel phrase while speaking: {text!r}"
            logger.info("Decision.INTERRUPT: %s", reason)
            return (Decision.INTERRUPT, reason)

        # Agent is silent – even pure backchannels are treated as valid input.
        reason = f"valid input while silent: {text!r}"
        logger.info("Decision.RESPOND: %s", reason)
        return (Decision.RESPOND, reason)

    def is_backchannel(self, text: str) -> bool:
        """Quick check if text is a short pure backchannel."""

        tokens = _tokenize(text)
        return (
            0 < len(tokens) <= 2
            and all(t in config.BACKCHANNEL_WORDS for t in tokens)
        )


