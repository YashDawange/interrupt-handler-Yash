import asyncio
from livekit.agents.voice.interrupt_handler import InterruptHandler

class FakePlayer:
    def __init__(self):
        self.is_playing_tts = True   # simulate: agent is speaking

    def is_playing(self):
        return self.is_playing_tts

    async def stop(self):
        print("[PLAYER] STOP TTS")

class FakeSession:
    def __init__(self):
        self.player = FakePlayer()

    async def on_interrupt(self, transcript, reason):
        print(f"[INTERRUPT] transcript='{transcript}', reason={reason}")

async def main():
    session = FakeSession()
    handler = InterruptHandler(
        get_agent_state_callable=lambda: session.player.is_playing()
    )

    # Attach interrupt callback
    handler._do_interrupt = lambda sid, transcript="", reason="": \
        asyncio.create_task(session.on_interrupt(transcript, reason))

    print("\n=== TEST 1: AGENT SPEAKING + 'yeah' ===")
    await handler.on_vad_start("sid")
    await handler.on_transcript("sid", "yeah", is_final=True)

    print("\n=== TEST 2: AGENT SPEAKING + 'stop please' ===")
    await handler.on_vad_start("sid2")
    await handler.on_transcript("sid2", "stop please", is_final=True)

    print("\n=== TEST 3: AGENT SILENT + 'yeah' ===")
    session.player.is_playing_tts = False
    res = await handler.on_transcript("sid3", "yeah", is_final=True)
    print("[OUTPUT]", res)


asyncio.run(main())
