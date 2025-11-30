# run_worker.py
'''
import asyncio
import os
from livekit.agents import WorkerOptions, AgentServer, JobContext

from my_agent import ControlledAgent, ControlledAgentSession


async def entrypoint(ctx: JobContext):
    """LiveKit worker-job entrypoint."""

    # Connect using job token
    await ctx.connect()

    # Room is provided by the Job dispatcher
    room = ctx.room
    await room.wait_until_ready()

    session = ControlledAgentSession()
    await session.start(
        agent=ControlledAgent(),
        room=room,
    )


if __name__ == "__main__":
    options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        ws_url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
    )

    server = AgentServer.from_server_options(options)
    print("Worker booted")
    asyncio.run(server.run())
'''

# run_worker.py (DIRECT MODE TESTING)
import asyncio
import os
from interrupt_handler import ControlledAgentSession, ControlledAgent
from livekit import api

async def main():
    server_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    room_name = os.getenv("ROOM_NAME", "test_room")

    # Create access token
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity("agent-bot")
        .with_name("VoiceAgent")
        .with_grants(
            api.VideoGrants(
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )

    from livekit import Room
    room = Room(server_url, token)
    await room.connect()

    print("Agent connected to LiveKit room:", room_name)

    # Start session
    session = ControlledAgentSession()
    await session.start(
        agent=ControlledAgent(),
        room=room,
    )

    print("Agent is running...")

    # Keep alive
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
