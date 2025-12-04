import enum
from typing import List


class TimeoutFallback(enum.Enum):
    """Behavior when no STT text arrives before the buffer timeout."""

    IGNORE = "ignore"
    INTERRUPT = "interrupt"


# potential interruption.
BACKCHANNEL_WORDS: List[str] = [
    "yeah",
    "yep",
    "yup",
    "yes",
    "ok",
    "okay",
    "alright",
    "right",
    "sure",
    "fine",
    "cool",
    "nice",
    "great",
    "gotcha",
    "gotit",
    "gotcha",
    "hmm",
    "mhm",
    "mmhmm",
    "uh-huh",
    "uhhuh",
    "uh",
    "huh",
    "understood",
    "okaythen",
]

INTERRUPT_WORDS: List[str] = [
    "stop",
    "wait",
    "no",
    "nope",
    "cancel",
    "enough",
    "quiet",
    "silence",
    "hold",
    "pause",
    "hang",
    "listen",
    "excuse",
]

# Time to wait for STT confirmation after VAD fires (milliseconds)
BUFFER_TIMEOUT_MS: int = 200000

# Minimum number of tokens to consider a phrase as long content
MIN_PHRASE_LENGTH: int = 3

# Fallback behavior on timeout while agent is speaking
TIMEOUT_FALLBACK: TimeoutFallback = TimeoutFallback.INTERRUPT


