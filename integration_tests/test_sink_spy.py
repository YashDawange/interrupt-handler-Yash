import importlib.machinery
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "livekit-agents" / "livekit" / "agents" / "voice" / "interrupt_handler.py"
loader = importlib.machinery.SourceFileLoader("interrupt_handler", str(MOD_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
ih = importlib.util.module_from_spec(spec)
loader.exec_module(ih)


class Spy:
    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1


def test_no_interrupt_pause_called_for_filler():
    interrupt_spy = Spy()
    pause_spy = Spy()

    # Simulate scenario: agent is speaking and user utterance is filler
    utterance = "yeah"
    cls = ih.classify_transcript(utterance)
    assert cls == "ignore"

    # In the real pipeline, the interrupt/pause sinks would be invoked only if cls == 'interrupt'
    if cls == "interrupt":
        interrupt_spy()
        pause_spy()

    assert interrupt_spy.calls == 0
    assert pause_spy.calls == 0
