import asyncio
from livekit.agents.voice.interrupt_handler import InterruptHandler

# Mock VAD Event class
class FakeVADEvent:
    def __init__(self, type):
        self.type = type

class FakeVADType:
    START_OF_SPEECH = "start"
    INFERENCE_DONE = "inf"
    END_OF_SPEECH = "end"

async def test_vad_interrupt():
    # Simulate agent IS speaking
    handler = InterruptHandler(lambda: True)

    print("\n=== TEST VAD: START OF SPEECH WHILE AGENT SPEAKING ===")
    result = await handler.on_vad_start("demo_session")

    print("RESULT:", result)
    expected = {"action": "treat_as_user_turn", "reason": "agent_silent_on_vad"}

    print("EXPECTED:", expected)

asyncio.run(test_vad_interrupt())
