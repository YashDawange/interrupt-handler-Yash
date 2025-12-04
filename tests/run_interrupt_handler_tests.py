import asyncio
import importlib.machinery
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "livekit-agents" / "livekit" / "agents" / "voice" / "interrupt_handler.py"
loader = importlib.machinery.SourceFileLoader("interrupt_handler", str(MOD_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
ih = importlib.util.module_from_spec(spec)
loader.exec_module(ih)


def assert_eq(a, b, msg=None):
    if a != b:
        raise AssertionError(msg or f"{a!r} != {b!r}")


def test_classify():
    assert_eq(ih.classify_transcript("yeah"), "ignore")
    assert_eq(ih.classify_transcript("uh-huh"), "ignore")
    assert_eq(ih.classify_transcript("please stop"), "interrupt")
    assert_eq(ih.classify_transcript("wait a second"), "interrupt")
    assert_eq(ih.classify_transcript("i like pizza"), "unknown")
    print("classify_transcript tests passed")


async def test_defer_immediate():
    class DummyAR:
        @property
        def current_transcript(self):
            return "yeah"

    res = await ih.defer_vad_decision(DummyAR(), speaking=True)
    assert_eq(res, "ignore")
    print("defer_vad_decision immediate test passed")


async def test_defer_waits():
    # shorten window so test is fast
    ih.VALIDATION_WINDOW_MS = 100

    class DummyAR:
        def __init__(self):
            self._transcript = ""

        @property
        def current_transcript(self):
            return self._transcript

    ar = DummyAR()

    async def set_late():
        await asyncio.sleep(0.02)
        ar._transcript = "stop"

    task = asyncio.create_task(set_late())
    res = await ih.defer_vad_decision(ar, speaking=True)
    await task
    assert_eq(res, "interrupt")
    print("defer_vad_decision wait-for-partial test passed")


async def main():
    test_classify()
    await test_defer_immediate()
    await test_defer_waits()


if __name__ == "__main__":
    asyncio.run(main())
