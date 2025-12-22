import string

class InterruptionManager:
    # Decoupled logic for handling interruption signals.
    # Determines if user input should stop the agent or be ignored (backchanneling).
    def __init__(self, ignore_words):
        self.ignore_words = ignore_words
        # This helper removes punctuation (turns "Okay." into "Okay")
        self.strip_punct = str.maketrans('', '', string.punctuation)

    def should_interrupt(self, transcript: str, is_speaking: bool) -> bool:
        # If agent is not speaking, we never interrupt.
        if not is_speaking:
            return False

        # Clean the text (remove punctuation and make lowercase)
        clean_text = transcript.translate(self.strip_punct).lower().strip()
        
        if not clean_text:
            return False
        
        words = clean_text.split()

        # If EVERY word is in the ignore list, do NOT interrupt.
        # (e.g. "Yeah" or "Okay sure")
        if all(w in self.ignore_words for w in words):
            return False 

        # Otherwise, it's a real command. STOP!
        return True