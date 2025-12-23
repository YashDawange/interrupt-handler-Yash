# config.py

# -------- interrupt scoring weights --------

INTERRUPT_WORD_WEIGHT = 1.0
PASSIVE_WORD_WEIGHT = -0.5

# -------- decision timing --------

# Maximum time (seconds) to wait for STT before deciding
INTERRUPT_DECISION_TIMEOUT = 0.6

# -------- word categories --------

# Strong signals that should interrupt immediately
INTERRUPT_WORDS = {
    "stop",
    "wait",
    "pause",
    "cancel",
    "no",
    "hold",
    "hold on",
}

# Passive acknowledgements that should NOT interrupt
PASSIVE_WORDS = {
    "yeah",
    "yes",
    "ok",
    "okay",
    "hmm",
    "uh",
    "uh-huh",
    "right",
    "mm-hmm",
}
