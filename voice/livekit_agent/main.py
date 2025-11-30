
# livekit_agent/main.py
import logging
from .server import server   # import the AgentServer instance
import asyncio

logger = logging.getLogger("livekit-agent.main")

def _handle_async_exception(loop, context):
    logger.error("UNHANDLED ASYNC EXCEPTION: %s", context)

# set the loop exception handler early
loop = asyncio.get_event_loop()
loop.set_exception_handler(_handle_async_exception)

if __name__ == "__main__":
    logger.info("Starting agent server (CLI)")
    from livekit.agents import cli
    cli.run_app(server)