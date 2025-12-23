import logging
from typing import List

from config import IGNORE_WORDS, INTERRUPT_WORDS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interrupt-agent")


class InterruptHandler:
    def __init__(self):
        self.agent_is_speaking = False

    def normalize(self, text: str) -> List[str]:
        return text.lower().strip().split()

    def contains_only_ignore_words(self, tokens: List[str]) -> bool:
        return all(w in IGNORE_WORDS for w in tokens)

    def contains_interrupt(self, tokens: List[str]) -> bool:
        return any(w in INTERRUPT_WORDS for w in tokens)

    def on_agent_tts_start(self):
        self.agent_is_speaking = True
        logger.info("Agent speaking")

    def on_agent_tts_end(self):
        self.agent_is_speaking = False
        logger.info("Agent silent")

    def on_user_input(self, text: str) -> str:
        tokens = self.normalize(text)
        logger.info(f"User said: {text}")

        if self.agent_is_speaking:
            if self.contains_interrupt(tokens):
                logger.info("Hard interrupt detected")
                return "INTERRUPT"

            if self.contains_only_ignore_words(tokens):
                logger.info("Ignoring backchannel")
                return "IGNORE"

            logger.info("Interrupting due to unknown speech")
            return "INTERRUPT"

        logger.info("Responding normally")
        return f"RESPOND: {text}"


# ---------------- TEST RUNNER ----------------
if __name__ == "__main__":
    handler = InterruptHandler()

    print("\n=== Interactive Interrupt Handler ===")
    print("Commands:")
    print("  /speak   -> agent starts speaking")
    print("  /silent  -> agent stops speaking")
    print("  /exit    -> quit\n")

    while True:
        user_input = input("You: ").strip()

        if user_input == "/exit":
            break

        if user_input == "/speak":
            handler.on_agent_tts_start()
            print("Agent is now SPEAKING")
            continue

        if user_input == "/silent":
            handler.on_agent_tts_end()
            print("Agent is now SILENT")
            continue

        result = handler.on_user_input(user_input)
        print("Result:", result)
