import os
from dotenv import load_dotenv

# Force reload
load_dotenv(override=True)

print("--- ENV CHECK ---")
url = os.getenv("LIVEKIT_URL")
print(f"LIVEKIT_URL: '{url}'")

if url == "wss://your-project.livekit.cloud":
    print("ERROR: Still seeing default placeholder URL!")
elif url and "voice-agent-demo" in url:
    print("SUCCESS: URL looks correct.")
else:
    print("WARNING: URL is set but looks unusual.")

print(f"Current Working Directory: {os.getcwd()}")
print(f"File .env exists: {os.path.exists('.env')}")
