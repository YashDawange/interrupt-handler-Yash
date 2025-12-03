# examples/simulate_vad_stt.py
import asyncio
from livekit_agents.interrupt_filter import InterruptFilter  # adjust import if path differs
# If your file is at livekit-agents/livekit/agents/interrupt_filter.py
# and Python can't import that path, change to: from interrupt_filter import InterruptFilter
# or add repo root to PYTHONPATH before running the script.

async def main():
    def on_interrupt(text):
        print("[DECISION] INTERRUPT -> text:", repr(text))

    def on_ignore():
        print("[DECISION] IGNORE -> continue speaking")

    f = InterruptFilter(on_interrupt=on_interrupt, on_ignore=on_ignore, stt_timeout_ms=200)

    # Case 1: agent speaking, VAD triggers, user says filler -> IGNORE
    print("=== Case 1: agent speaking + filler word ===")
    f.set_agent_speaking(True)
    await f.on_vad_trigger()
    await f.on_stt_partial("yeah", is_final=True)
    await asyncio.sleep(0.25)

    # Case 2: agent speaking, VAD triggers, user interrupts -> INTERRUPT
    print("\n=== Case 2: agent speaking + interrupt word ===")
    f.set_agent_speaking(True)
    await f.on_vad_trigger()
    await f.on_stt_partial("no stop", is_final=True)
    await asyncio.sleep(0.25)

    # Case 3: agent silent, VAD triggers -> PASS_THROUGH
    print("\n=== Case 3: agent silent + filler (should be PASS_THROUGH) ===")
    f.set_agent_speaking(False)
    res = await f.on_vad_trigger()
    print("on_vad_trigger returned:", res)

if __name__ == "__main__":
    asyncio.run(main())
