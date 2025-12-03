# examples/simulate_vad_stt.py
import asyncio
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path so we can import the module we created.
# __file__ is examples/simulate_vad_stt.py; repo_root = ../
repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Try to import the interrupt filter from the installed package layout first,
# then fall back to loading the file directly by path if necessary.
try:
    # The package inside the repo is "livekit" (under livekit-agents/livekit)
    from livekit.agents.interrupt_filter import InterruptFilter
except Exception:
    try:
        # Some setups may expose the module as 'interrupt_filter' directly if placed at repo root.
        from interrupt_filter import InterruptFilter  # type: ignore
    except Exception:
        # Last resort: load the file by path.
        import importlib.util

        fallback_path = os.path.join(
            repo_root, "livekit-agents", "livekit", "agents", "interrupt_filter.py"
        )
        spec = importlib.util.spec_from_file_location("interrupt_filter", fallback_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot find interrupt_filter.py at {fallback_path}")
        interrupt_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(interrupt_mod)  # type: ignore
        InterruptFilter = interrupt_mod.InterruptFilter  # type: ignore

async def main():
    def on_interrupt(text):
        print("[DECISION] INTERRUPT -> text:", repr(text))

    def on_ignore():
        print("[DECISION] IGNORE -> continue speaking")

    f = InterruptFilter(on_interrupt=on_interrupt, on_ignore=on_ignore, stt_timeout_ms=200)

    print("=== Case 1: agent speaking + filler word ===")
    f.set_agent_speaking(True)
    await f.on_vad_trigger()
    await f.on_stt_partial("yeah", is_final=True)
    await asyncio.sleep(0.25)

    print("\n=== Case 2: agent speaking + interrupt word ===")
    f.set_agent_speaking(True)
    await f.on_vad_trigger()
    await f.on_stt_partial("no stop", is_final=True)
    await asyncio.sleep(0.25)

    print("\n=== Case 3: agent silent + filler ===")
    f.set_agent_speaking(False)
    res = await f.on_vad_trigger()
    print("on_vad_trigger returned:", res)

if __name__ == "__main__":
    asyncio.run(main())
