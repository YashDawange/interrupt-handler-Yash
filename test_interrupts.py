import asyncio
from livekit.agents.voice.interrupt_handler import InterruptHandler

async def test_interrupts():
    handler = InterruptHandler(lambda: True)

    print("TEST 1:", await handler.on_transcript("demo", "yeah okay", False))
    print("TEST 2:", await handler.on_transcript("demo", "wait wait", False))
    print("TEST 3:", await handler.on_transcript("demo", "yeah hmm but stop", False))

asyncio.run(test_interrupts())

