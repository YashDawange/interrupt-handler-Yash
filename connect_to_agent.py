"""
Simple script to connect to the interruption test agent.
This will print a URL you can open in your browser to test.
"""

import os
from livekit import api
from pathlib import Path

# Load .env file if it exists
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

# Get credentials from environment
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# Create a room token for testing
room_name = "test-interruption"
token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
token.with_identity("test-user")
token.with_name("Test User")
token.with_grants(api.VideoGrants(
    room_join=True,
    room=room_name,
    can_publish=True,
    can_subscribe=True,
))

jwt_token = token.to_jwt()

# Print the connection URL
playground_url = f"https://agents-playground.livekit.io/?url={LIVEKIT_URL}&token={jwt_token}"

print("=" * 80)
print("INTERRUPTION TEST AGENT - CONNECTION INFO")
print("=" * 80)
print()
print("1. Open this URL in your browser:")
print()
print(playground_url)
print()
print("2. Click 'Connect' in the browser")
print()
print("3. Test interruptions:")
print("   - Say: 'Tell me a long story about space exploration'")
print("   - While agent is speaking, interrupt with: 'Wait!' or 'Stop!'")
print("   - Watch the console for interruption events")
print()
print("=" * 80)
print()
print("Room name:", room_name)
print("Your identity: test-user")
print()
print("Press Ctrl+C to exit")
print("=" * 80)
