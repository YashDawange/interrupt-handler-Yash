import os
import asyncio
from dotenv import load_dotenv
from livekit import api

async def main():
    load_dotenv(override=True)
    
    # Create a token
    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET")
    ).with_identity("human-user").with_name("Human").with_grants(
        api.VideoGrants(
            room_join=True,
            room="my-room",
        )
    )
    
    jwt = token.to_jwt()
    print(f"\n--- ROOM TOKEN ---\n{jwt}\n------------------\n")
    print(f"URL: {os.getenv('LIVEKIT_URL')}")

if __name__ == "__main__":
    asyncio.run(main())
