import os

def _split_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [w.strip().lower() for w in value.split(",") if w.strip()]

# Soft backchannel words: ignored while the agent is speaking
DEFAULT_IGNORE_WORDS = {"yeah", "yea", "ok", "okay", "hmm", "uh-huh", "uh huh", "right"}

# Hard interruption keywords: stop the agent immediately while speaking
DEFAULT_INTERRUPT_WORDS = {"stop", "wait", "no", "hold on", "one second"}

# These can be overridden using environment variables
IGNORE_WORDS: set[str] = (
    set(_split_env_list(os.getenv("INTERRUPT_IGNORE_WORDS")))
    or DEFAULT_IGNORE_WORDS
)

INTERRUPT_WORDS: set[str] = (
    set(_split_env_list(os.getenv("INTERRUPT_COMMAND_WORDS")))
    or DEFAULT_INTERRUPT_WORDS
)
