import re
import os

class InterruptionHandler:
    def __init__(self):
        self.default_ignore = {'yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'right', 'aha', 'yep'}
        env_ignore = os.getenv('IGNORE_WORDS')
        
        if env_ignore:
            self.ignore_words = set(word.strip().lower() for word in env_ignore.split(','))
        else:
            self.ignore_words = self.default_ignore

    def should_interrupt(self, user_transcript: str, is_agent_speaking: bool) -> str:
        # FIX: Added '-' to the regex to preserve "uh-huh"
        clean_text = re.sub(r'[^\w\s-]', '', user_transcript).lower().strip()
        
        if not clean_text:
            return "IGNORE"

        words = clean_text.split()
        
        # Check if ALL words are in the ignore list
        is_pure_backchannel = all(word in self.ignore_words for word in words)

        if is_agent_speaking:
            if is_pure_backchannel:
                return "IGNORE"
            else:
                return "INTERRUPT"
        else:
            return "RESPOND"