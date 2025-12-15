import asyncio
import os
from dotenv import load_dotenv
from livekit import rtc, api

# Load API Keys
load_dotenv()
URL = os.getenv("LIVEKIT_URL")
API_KEY = os.getenv("LIVEKIT_API_KEY")
API_SECRET = os.getenv("LIVEKIT_API_SECRET")

async def run_test():
    print("\n🤖 STARTING AUTOMATED PROOF GENERATOR 🤖")
    print("------------------------------------------")

    # 1. Generate Token
    token = (
        api.AccessToken(API_KEY, API_SECRET)
        .with_identity("proof-generator")
        .with_name("Test Bot")
        .with_grants(api.VideoGrants(room_join=True, room="test-room"))
        .to_jwt()
    )

    # 2. Connect
    room = rtc.Room()
    print(f"📡 Connecting to LiveKit Room...")
    try:
        await room.connect(URL, token)
        print("✅ Connected successfully.\n")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return

    chat = rtc.ChatManager(room)

    # --- PHASE 1: TRIGGER AGENT ---
    print("🗣️  Step 1: Asking Agent to speak...")
    await chat.send_message("Tell me a very long story about history.")
    print("   -> Sent: 'Tell me a very long story...'")
    print("⏳  Waiting 3 seconds for Agent to start talking...")
    await asyncio.sleep(3)

    # --- PHASE 2: TEST PASSIVE IGNORE (SCENARIO 1) ---
    print("\n🧪 Step 2: Testing SCENARIO 1 (Passive 'Yeah')...")
    print("   -> Sending: 'Yeah'")
    await chat.send_message("Yeah")
    print("👀  CHECK AGENT TERMINAL NOW! You should see '[SCENARIO 1 PASS]'")
    
    print("⏳  Waiting 3 seconds (Agent should STILL be talking)...")
    await asyncio.sleep(3)

    # --- PHASE 3: TEST INTERRUPTION (SCENARIO 3/4) ---
    print("\n🧪 Step 3: Testing SCENARIO 3 (Active 'Stop')...")
    print("   -> Sending: 'Stop immediately'")
    await chat.send_message("Stop immediately")
    print("👀  CHECK AGENT TERMINAL NOW! You should see '[SCENARIO 3 PASS]'")

    print("\n✅ TEST COMPLETE.")
    print("📸  TAKE A SCREENSHOT OF YOUR AGENT TERMINAL NOW!")
    
    await room.disconnect()

if __name__ == "__main__":
    asyncio.run(run_test())