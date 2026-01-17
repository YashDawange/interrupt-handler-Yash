import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InterruptionHandler:
    
    DEFAULT_IGNORE_WORDS = [
        "yeah", "ok", "okay", "hmm", "uh-huh", "right", 
        "aha", "mhmm", "yep", "yup", "sure", "gotcha"
    ]
    
    def __init__(self, ignore_words=None):
        self.ignore_words = set(
            word.lower() for word in (ignore_words or self.DEFAULT_IGNORE_WORDS)
        )
        self.agent_is_speaking = False
        logger.info(f"Handler initialized with {len(self.ignore_words)} ignore words")
    
    def set_agent_speaking(self, is_speaking):
        if self.agent_is_speaking != is_speaking:
            logger.debug(f"Agent state: speaking={is_speaking}")
            self.agent_is_speaking = is_speaking
    
    def should_interrupt(self, user_text):
        if not user_text or not user_text.strip():
            logger.debug("Empty input")
            return False
        
        text = user_text.lower().strip()
        
        if not self.agent_is_speaking:
            logger.info(f"Agent silent, accepting: '{text}'")
            return True
        
        words = text.split()
        
        all_ignored = all(w in self.ignore_words for w in words)
        
        if all_ignored:
            logger.info(f"Ignoring backchannel: '{text}'")
            return False
        else:
            logger.info(f"Valid interrupt: '{text}'")
            return True
    
    def add_ignore_word(self, word):
        self.ignore_words.add(word.lower())
        logger.info(f"Added '{word}' to ignore list")
    
    def remove_ignore_word(self, word):
        self.ignore_words.discard(word.lower())
        logger.info(f"Removed '{word}' from ignore list")
    
    def get_ignore_words(self):
        return sorted(list(self.ignore_words))


if __name__ == "__main__":
    print("=== Interruption Handler Tests ===\n")
    
    h = InterruptionHandler()
    
    tests = [
        (True, "yeah", False),
        (True, "ok", False),
        (True, "hmm yeah ok", False),
        (True, "yeah wait", True),
        (True, "stop", True),
        (False, "yeah", True),
        (False, "hello", True),
        (True, "yeah but wait", True),
    ]
    
    print("Running tests:\n")
    for speaking, inp, expected in tests:
        h.set_agent_speaking(speaking)
        result = h.should_interrupt(inp)
        status = "✓" if result == expected else "✗"
        state = "SPEAKING" if speaking else "SILENT"
        action = "INTERRUPT" if result else "IGNORE"
        
        print(f"{status} Agent {state:8} | '{inp:15}' → {action}")
    
    print("\n Tests Complete ")
