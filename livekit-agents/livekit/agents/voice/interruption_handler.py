import os

IGNORE_WORDS = set(os.getenv("IGNORE_WORDS_ENV", "yeah,ok,okay,hmm,uh-huh,right").split(","))
INTERRUPT_WORDS = set(os.getenv("INTERRUPT_WORDS_ENV", "stop,wait,no,hold on").split(","))

def classify_user_transcript(transcript: str):
    # Clean and lowercase
    cleaned = transcript.strip().lower()
    words = set(cleaned.replace('-', ' ').replace(',', ' ').split())
    if not words:
        return "IGNORE"
    # If ANY interrupt word present, treat as interrupt
    if any(word in INTERRUPT_WORDS for word in words):
        return "INTERRUPT"
    # Only if ALL are ignore, treat as ignore
    if all(word in IGNORE_WORDS for word in words):
        return "IGNORE"
    return "RESPOND"
