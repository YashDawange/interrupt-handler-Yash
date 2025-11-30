import logging
from livekit.agents.llm import function_tool
from livekit.agents import RunContext
from .config import logger as pkg_logger

logger = logging.getLogger("livekit-agent.agent")


class MyAgentBase:
    """A small wrapper so the Agent inheritance can remain isolated and testable."""
    def __init__(self, agent_obj):
        self._agent = agent_obj


# Using direct inheritance to match original behaviour
from livekit.agents import Agent


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. Read continuously; ignore backchannels while speaking; "
                "accept backchannels as answers when silent and recently asked a question."
            )
        )

    async def on_enter(self):
        logger.info("Agent.on_enter: starting opening generation (interruptible).")
        await self.generate_reply(allow_interruptions=True)

    @function_tool
    async def lookup_weather(self, context: RunContext, location: str):
        logger.debug("lookup_weather called location=%s", location)
        return "sunny with a temperature of 70 degrees."
