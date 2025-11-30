from livekit.agents import AgentServer
from .session_manager import entrypoint, prewarm
from .config import logger

server = AgentServer()
server.setup_fnc = prewarm
server.rtc_session()(entrypoint)  # attach entrypoint as rtc_session handler
