from typing import Set

# =============================================================================
# INTERRUPT HANDLER CONFIG
# =============================================================================

DEFAULT_BACKCHANNEL_WORDS: Set[str] = {
    "yeah", "yea", "yes", "yep", "yup",
    "ok", "okay", "alright", "aight",
    "hmm", "hm", "mhm", "mmhmm", "uh-huh", "uhuh",
    "right", "sure", "gotcha", "got it",
    "aha", "ah", "oh", "ooh",
    "mm", "mhmm", "huh"
}

DEFAULT_COMMAND_WORDS: Set[str] = {
    "stop", "wait", "hold", "pause",
    "no", "nope", "don't",
    "hold on", "wait a second", "wait a minute",
    "hang on", "one second", "one minute"
}

# =============================================================================
# HELPER / PATCH CONFIG
# =============================================================================

BACKCHANNEL_WORDS: Set[str] = {
    "yeah", "yea", "yes", "yep", "yup",
    "ok", "okay", "alright", "aight",
    "hmm", "hm", "mhm", "mmhmm", "uh-huh", "uhuh", "uh", "huh",
    "right", "sure", "gotcha",
    "aha", "ah", "oh", "ooh",
    "mm", "mhmm", "mmm", "hey"
}

COMMAND_WORDS: Set[str] = {
    "stop", "wait", "hold", "pause",
    "no", "nope", "don't"
}
