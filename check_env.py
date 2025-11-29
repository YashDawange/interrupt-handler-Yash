from dotenv import load_dotenv
import os

load_dotenv()

keys = [
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "OPENAI_API_KEY",
    "DEEPGRAM_API_KEY",
    "CARTESIA_API_KEY"
]

print("Checking environment variables...")
for key in keys:
    value = os.getenv(key)
    if value:
        print(f"{key}: SET (Length: {len(value)})")
        if value.startswith("<") or value.endswith(">"):
            print(f"WARNING: {key} seems to contain placeholder characters '<' or '>'")
    else:
        print(f"{key}: NOT SET")
