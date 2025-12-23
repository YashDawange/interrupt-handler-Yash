PASSIVE_ACKS = {
    "yeah",
    "ok",
    "okay",
    "hmm",
    "uh-huh",
    "mm-hmm",
    "right",
}
INTERRUPT_KEYWORDS = {
    "stop",
    "wait",
    "no",
    "cancel",
    "hold",
    "hold on",
}
def normalize(text: str) -> set[str]:
    return set(text.lower().strip().split())
def is_passive_ack(text: str) -> bool:
    words = normalize(text)
    return bool(words) and words.issubset(PASSIVE_ACKS)
def is_real_interruption(text: str) -> bool:
    words = normalize(text)
    return bool(words & INTERRUPT_KEYWORDS)