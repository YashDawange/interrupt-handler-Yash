import re

class SemanticClassifier:
    def __init__(self, ignore_words=None):
        # 1. Configurable Ignore List (The "Soft" inputs)
        if ignore_words is None:
            self.ignore_words = {
                'yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'right', 'aha', 'yep', 'cool', 'sure', 'got it'
            }
        else:
            self.ignore_words = set(w.lower() for w in ignore_words)

    def should_interrupt(self, text: str, is_agent_speaking: bool) -> bool:
        """
        Determines if the agent should stop speaking based on user input.
        Returns: True (Interrupt) or False (Ignore/Continue)
        """
        clean_text = self._clean_text(text)
        
        # If no text detected, don't interrupt
        if not clean_text:
            return False

        # --- THE LOGIC MATRIX ---
        
        # Scenario: Agent is Silent 
        # Result: Always process input (We never "interrupt" silence, we just reply)
        if not is_agent_speaking:
            return False 

        # Scenario: Agent is Speaking
        if is_agent_speaking:
            # Check 1: Is it a "passive acknowledgement"? (e.g., "Yeah")
            if clean_text in self.ignore_words:
                return False # IGNORE -> Agent keeps talking
            
            # Check 2: Is it a "Mixed Input"? (e.g., "Yeah wait a second")
            # If it starts with an ignore word but has more meaningful content, INTERRUPT.
            words = clean_text.split()
            if words[0] in self.ignore_words and len(words) > 1:
                return True # SEMANTIC INTERRUPTION
            
            # Check 3: Is it a direct command? (e.g., "Stop")
            return True # INTERRUPT

        return False

    def _clean_text(self, text: str) -> str:
        # Simple normalization: remove punctuation, lowercase, strip whitespace
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip().lower()