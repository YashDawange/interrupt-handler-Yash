import asyncio, os
from stt_engine import get_stt
from tts_engine import TTSEngine
from livekit_agent import LiveKitAgent

async def main():
    use_sim = os.getenv("USE_SIMULATION","true").lower() in ("1","true","yes")
    stt = get_stt(allow_sim=use_sim)
    tts = TTSEngine()
    agent = LiveKitAgent(stt, tts, room_name=os.getenv("ROOM_NAME","voice-room"))

    if use_sim:
        print("Running in SIMULATION mode. No LiveKit connection.")
        await agent.run_simulation()
    else:
        print("Running in LIVE LiveKit mode. Attempting to connect to LiveKit server")
        await agent.run_live()

if __name__ == '__main__':
    asyncio.run(main())
