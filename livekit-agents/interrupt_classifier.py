from interrupt_config import IGNORE_WORDS, INTERRUPT_WORDS

def classify_text(text: str, speaking: bool) -> str:
    if not text:
        return "IGNORE"

    text = text.lower().strip()
    words = text.split()

    # stop should always interrupt
    for word in words:
        if word in INTERRUPT_WORDS:
            return "INTERRUPT"

    # ignore fillers ONLY if agent is speaking
    if speaking:
        for word in words:
            if word in IGNORE_WORDS:
                return "IGNORE"

    # otherwise treat as real response
    return "RESPONSE"

