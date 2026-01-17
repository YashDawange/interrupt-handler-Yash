# interrupt_handler.py

SOFT_ACK_WORDS = {
    "yeah", "ok", "okay", "hmm", "uh-huh", "right"
}

HARD_INTERRUPT_WORDS = {
    "stop", "wait", "no", "pause", "cancel"
}


def normalize(text: str) -> list[str]:
    return (
        text.lower()
        .replace(".", "")
        .replace(",", "")
        .strip()
        .split()
    )


def should_interrupt(text: str) -> bool:
    tokens = normalize(text)

    # Hard interrupt always wins
    if any(word in HARD_INTERRUPT_WORDS for word in tokens):
        return True

    # Only soft acknowledgements → ignore
    if tokens and all(word in SOFT_ACK_WORDS for word in tokens):
        return False

    # Mixed or unknown input → interrupt
    return True
