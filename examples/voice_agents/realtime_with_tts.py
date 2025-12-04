import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("console-agent")

IGNORE_WORDS = ["yeah", "ya", "haan", "hmm"]


def should_interrupt(text: str) -> bool:
    t = text.lower().strip()
    if t in IGNORE_WORDS:
        return False
    return True


class ConsoleAgent:
    def __init__(self):
        self.speaking = False
        self.speaking_rate = 0.05

    async def speak(self, text: str):
        duration = min(len(text) * self.speaking_rate, 4)
        logger.info(f"Assistant speaking: {text} ({duration:.2f}s)")
        self.speaking = True
        await asyncio.sleep(duration)
        self.speaking = False
        logger.info("Assistant finished speaking.")

    async def reply(self, user_text: str):
        t = user_text.lower()
        if "weather" in t:
            return "The weather is sunny."
        if "mumbai" in t:
            return "Mumbai is located on the west coast of India."
        if "stop" in t:
            return "Stopping now."
        return f"You said: {user_text}"


async def main():
    agent = ConsoleAgent()
    await agent.speak("Hello, I am your assistant. Start speaking.")

    while True:
        user = await asyncio.to_thread(input, "> ")

        if user.lower() == "quit":
            print("Exiting.")
            break

        if agent.speaking:
            if should_interrupt(user):
                logger.info("INTERRUPT TRIGGERED — stopping speech.")
                agent.speaking = False
            else:
                logger.info("Ignored filler word.")
                continue

        response = await agent.reply(user)
        await agent.speak(response)


if __name__ == "__main__":
    asyncio.run(main())
