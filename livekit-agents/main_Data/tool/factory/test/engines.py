"""
Simple unified test runner for all Engines.
Covers RULES, LLM, ML, RAG, and HYBRID modes.

Run:
    python3 test_run_engines.py
"""

import asyncio
import logging

from factory.engine_factory import EngineFactory

logging.basicConfig(level=logging.INFO)


async def test_engine(mode: str):
    print("\n" + "=" * 60)
    print(f"🔧 Testing Engine Mode: {mode}")
    print("=" * 60)

    try:
        engine = EngineFactory.get_engine(mode)
    except Exception as e:
        print(f"❌ Failed to initialize engine '{mode}': {e}")
        return

    test_cases = [
        ("stop please", True),
        ("yeah okay", True),
        ("tell me more", False)
    ]

    for transcript, agent_speaking in test_cases:
        print(f"\n⬤ Input: '{transcript}' | agent_speaking={agent_speaking}")
        try:
            result = await engine.classify(transcript, agent_speaking)
            print(f"➡ Result: {result}")
        except Exception as e:
            print(f"❌ Error during classify(): {e}")

    # close engine if needed
    try:
        await engine.close()
    except Exception:
        pass


async def main():
    modes = ["RULES", "LLM", "ML", "RAG", "HYBRID"]

    for mode in modes:
        await test_engine(mode)


if __name__ == "__main__":
    asyncio.run(main())
