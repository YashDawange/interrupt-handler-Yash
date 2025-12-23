"""
Interruption Policy Configuration

These word lists define conversational policy and are intentionally
kept separate from agent logic to allow easy updates.
"""

# Passive acknowledgements / backchannels
IGNORE_WORDS = {
    "yeah",
    "ok",
    "okay",
    "hmm",
    "right",
    "uh",
    "uhh",
    "uh-huh",
    "mhmm",
    "mhm",
    "yep",
    "yup",
    "aha",
    "alright",
}

# Explicit interruption or control commands
INTERRUPT_WORDS = {
    "stop",
    "wait",
    "no",
    "pause",
    "hold",
    "cancel",
    "but",
}
