import asyncio
import importlib.machinery
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "livekit-agents" / "livekit" / "agents" / "voice" / "interrupt_handler.py"
loader = importlib.machinery.SourceFileLoader("interrupt_handler", str(MOD_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
ih = importlib.util.module_from_spec(spec)
loader.exec_module(ih)


class DummySinks:
    def __init__(self):
        self.interrupted = False
        self.paused = False

    def interrupt(self):
        self.interrupted = True

    def pause(self):
        self.paused = True


async def test_interim_filler_does_not_interrupt():
    sinks = DummySinks()

    # simulate interim transcript while agent speaking
    cls = ih.classify_transcript("yeah")
    assert cls == "ignore"

    # only call interrupt if classification == 'interrupt'
    if cls == "interrupt":
        sinks.interrupt()

    assert not sinks.interrupted
    print("interim filler did not interrupt: OK")


async def test_interim_command_interrupts():
    sinks = DummySinks()

    cls = ih.classify_transcript("stop that")
    assert cls == "interrupt"

    if cls == "interrupt":
        sinks.interrupt()

    assert sinks.interrupted
    print("interim command interrupted: OK")


async def test_deferred_vad_with_late_command_triggers_interrupt():
    # Simulate audio_recognition with late transcript
    class AR:
        def __init__(self):
            self._t = ""

        @property
        def current_transcript(self):
            return self._t

    ar = AR()
    sinks = DummySinks()

    async def late_set():
        await asyncio.sleep(0.02)
        ar._t = "please stop"

    task = asyncio.create_task(late_set())
    # shorten the validation window for fast test
    ih.VALIDATION_WINDOW_MS = 100
    cls = await ih.defer_vad_decision(ar, speaking=True)
    await task

    if cls == "interrupt":
        sinks.interrupt()

    assert sinks.interrupted
    print("deferred VAD late command triggered interrupt: OK")


async def main():
    await test_interim_filler_does_not_interrupt()
    await test_interim_command_interrupts()
    await test_deferred_vad_with_late_command_triggers_interrupt()


if __name__ == "__main__":
    asyncio.run(main())
