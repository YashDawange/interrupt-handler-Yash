import re
from config import get_ignore_words

class InterruptionHandler:
    def __init__(self):
        self.ignore_words = get_ignore_words()

    def should_interrupt(self, text: str, is_agent_speaking: bool) -> bool:
        """
        Decides if the agent should stop speaking based on the user's input.
        
        Args:
            text (str): The raw transcribed text from the user.
            is_agent_speaking (bool): Whether the agent is currently generating/playing audio.
            
        Returns:
            bool: 
                - True if the input is a valid command (e.g., "Stop", "Wait").
                - False if the input is passive (e.g., "Yeah") or noise.
        """
        # 1. Clean the text (remove punctuation, lower case)
        cleaned_text = self._clean_text(text)
        
        # 2. Logic Matrix
        
        # Scenario: Agent is Silent
        if not is_agent_speaking:
            return True

        # Scenario: Agent is Speaking
        if is_agent_speaking:
            # If the text was just noise (empty string), ignore it.
            if not cleaned_text:
                return False
                
            if cleaned_text in self.ignore_words:
                return False 
            
            return True

        return True

    def _clean_text(self, text: str) -> str:
        """
        Normalizes text for comparison.
        "Okay." -> "okay"
        "Yeah!!" -> "yeah"
        """
        if not text:
            return ""
        # Remove all characters that are not word characters or whitespace
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip().lower()