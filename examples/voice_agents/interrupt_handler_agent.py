IGNORE_WORDS = {"yeah", "ok", "hmm", "uh-huh", "right" ,'aha'}
INTERRUPT_WORDS = {"stop", "wait", "no"}

def classify_user_input(text: str, agent_is_speaking: bool) -> str:
    text = text.lower().strip()
    tokens = text.split()

    if agent_is_speaking:
        if any(word in text for word in INTERRUPT_WORDS):
            return "INTERRUPT"
        if tokens and all(token in IGNORE_WORDS for token in tokens):
            return "IGNORE"
        return "INTERRUPT"
    else:
        return "RESPOND"


if __name__ == "__main__":
    tests = [
        ("yeah", True),
        ("ok hmm", True),
        ("yeah wait", True),
        ("stop", True),
        ("yeah", False),
        ("hello", False),
    ]

    for text, speaking in tests:
        print(
            f"text='{text}', speaking={speaking} → {classify_user_input(text, speaking)}"
        )
