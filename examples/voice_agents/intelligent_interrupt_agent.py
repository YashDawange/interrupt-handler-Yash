# examples/voice_agents/intelligent_interrupt_agent_fixed.py
import asyncio
import logging
from dotenv import load_dotenv

from livekit.agents import Agent, AgentSession, JobContext, cli, room_io
from livekit.agents.llm import function_tool
from interrupt_handler import should_interrupt  # your custom interruption logic

logger = logging.getLogger("intelligent-interrupt")
logger.setLevel(logging.INFO)

load_dotenv()


class MyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a helpful assistant.",
            llm=None,  # replace with your LLM plugin if installed
            tts=None,  # replace with your TTS plugin if installed
        )

    @function_tool
    async def get_weather(self, location: str):
        return f"The weather in {location} is sunny, 20°C."


async def main():
    session = AgentSession()
    agent_instance = MyAgent()

    await session.start(
        agent=agent_instance,
        room=None,  # or a proper room if you have one
        room_options=room_io.RoomOptions(
            text_output=True,
            audio_output=False,
        ),
    )

    # Example of handling user input
    user_text = "stop"
    agent_speaking = session.is_speaking()
    if should_interrupt(user_text, agent_speaking):
        await session.stop_speaking()
        await session.process_input(user_text)


if __name__ == "__main__":
    asyncio.run(main())
