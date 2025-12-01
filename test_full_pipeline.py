import asyncio
from livekit.agents.voice.interrupt_handler import InterruptHandler

# Mock TTS Player
class FakePlayer:
    def __init__(self):
        self.stopped = False
        self.speaking = True  # Simulate "agent is speaking"

    async def stop(self):
        print("[PLAYER] stop() called")
        self.stopped = True

    def is_playing(self):
        return self.speaking


# Mock AgentSession
class FakeSession:
    def __init__(self):
        self.player = FakePlayer()
        self.last_user_input = None
        
        self.interrupt_handler = InterruptHandler(
            get_agent_state_callable=lambda: self.player.is_playing()
        )

        # Attach callback for actual interruption
        self.interrupt_handler._do_interrupt = (
            lambda sid, transcript="", reason="": asyncio.create_task(
                self._on_interrupt(transcript, reason)
            )
        )

    async def _on_interrupt(self, transcript, reason):
        print(f"[SESSION] INTERRUPT received: '{transcript}' ({reason})")
        await self.player.stop()
        self.last_user_input = transcript


async def test_pipeline():
    session = FakeSession()

    print("\n=== TEST PIPELINE: 'yeah but stop please' ===")
    
    result = await session.interrupt_handler.on_transcript(
        "demo", "yeah but stop please", is_final=True
    )

    print("HANDLER RESULT:", result)
    print("PLAYER STOPPED:", session.player.stopped)
    print("USER INPUT FORWARDED:", session.last_user_input)


asyncio.run(test_pipeline())
