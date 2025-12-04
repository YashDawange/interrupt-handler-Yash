import asyncio
import importlib.machinery
import importlib.util
import pathlib
import sys

import pytest

# Load the module directly from file to avoid importing the package and running
# tests/conftest.py which pulls heavy project imports.
ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "livekit-agents" / "livekit" / "agents" / "voice" / "interrupt_handler.py"
loader = importlib.machinery.SourceFileLoader("interrupt_handler", str(MOD_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
ih = importlib.util.module_from_spec(spec)
loader.exec_module(ih)


def test_classify_transcript_ignore():
    assert ih.classify_transcript("yeah") == "ignore"
    assert ih.classify_transcript("uh-huh") == "ignore"
    assert ih.classify_transcript("mm") == "ignore"


def test_classify_transcript_interrupt():
    assert ih.classify_transcript("please stop") == "interrupt"
    assert ih.classify_transcript("wait a second") == "interrupt"


def test_classify_transcript_unknown():
    assert ih.classify_transcript("i like pizza") == "unknown"


@pytest.mark.asyncio
async def test_defer_vad_decision_immediate_transcript(monkeypatch):
    class DummyAR:
        @property
        def current_transcript(self):
            return "yeah"

    res = await ih.defer_vad_decision(DummyAR(), speaking=True)
    assert res == "ignore"


@pytest.mark.asyncio
async def test_defer_vad_decision_waits_for_partial(monkeypatch):
    # shorten the validation window to make the test fast
    monkeypatch.setattr(ih, "VALIDATION_WINDOW_MS", 100)

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
    assert res == "interrupt"
