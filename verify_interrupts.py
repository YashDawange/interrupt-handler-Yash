import asyncio
from livekit.agents.voice.interrupt_handler import InterruptHandler


async def main():
    handler = InterruptHandler(lambda: True)  # agent is speaking

    print("\nTEST 1: IGNORE WORDS")
    print(await handler.on_transcript("demo", "yeah okay", False))
    # expected: ignore

    print("\nTEST 2: PURE INTERRUPT WORDS")
    print(await handler.on_transcript("demo", "stop", True))
    print(await handler.on_transcript("demo", "wait please", True))
    # expected: interrupt

    print("\nTEST 3: MIXED PHRASE")
    print(await handler.on_transcript("demo", "yeah hmm but stop", True))
    # expected: interrupt


asyncio.run(main())

