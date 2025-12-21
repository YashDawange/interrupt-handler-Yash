
import string

class InterruptionHandler:
    def __init__(self, ignore_words: list[str] | None = None):
        self.ignore_words = set(ignore_words or [
            "yeah", "ok", "okay", "hmm", "aha", "uh-huh", "right", "sure", "yep", "yup"
        ])
        # Simple punctuation removal
        self.punc_table = str.maketrans("", "", string.punctuation)

    def should_interrupt(self, text: str) -> bool:
        """
        Determines if the text should cause an interruption.
        Returns True if the text contains meaningful content (not just filler words).
        Returns False if the text consists ONLY of ignored words.
        """
        if not text:
            return False
            
        # Normalize: lowercase, remove punctuation
        clean_text = text.lower().translate(self.punc_table).strip()
        if not clean_text:
            return False

        words = clean_text.split()
        if not words:
            return False

        # If any word is NOT in ignore list, it's an interruption (active command or mixed content)
        for w in words:
            if w not in self.ignore_words:
                return True
                
        # All words are in ignore list -> Ignore (Don't interrupt)
        return False
