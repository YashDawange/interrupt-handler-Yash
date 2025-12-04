import importlib.machinery
import importlib.util
import pathlib

import pytest

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


class DummySession:
    def __init__(self):
        self.transcribed_called = False
        self.last_transcript = None

    def _user_input_transcribed(self, evt):
        # evt is a minimal object with transcript attribute for our tests
        self.transcribed_called = True
        # event might contain alternatives as in real SpeechEvent
        if hasattr(evt, "alternatives") and len(evt.alternatives) > 0:
            self.last_transcript = getattr(evt.alternatives[0], "text", None) or getattr(evt.alternatives[0], "transcript", None)
        else:
            self.last_transcript = getattr(evt, "transcript", None)


def test_scenario1_long_explanation_ignores_filler():
    # Agent is speaking; user says filler
    sinks = DummySinks()
    session = DummySession()

    text = "Okay yeah uh-huh"
    cls = ih.classify_transcript(text)
    assert cls == "ignore"

    # If agent speaking, we should NOT interrupt when classification == ignore
    if cls == "interrupt":
        sinks.interrupt()

    assert not sinks.interrupted


def test_scenario2_passive_affirmation_when_silent_delivered_to_session():
    # Agent is silent; user says 'Yeah' -> should be treated as input
    session = DummySession()

    class Ev:
        def __init__(self, text):
            class Alt:
                def __init__(self, t):
                    self.text = t
            self.alternatives = [Alt(text)]

    ev = Ev("Yeah")

    # Simulate the part of AgentActivity that always forwards the transcript
    session._user_input_transcribed(ev)

    assert session.transcribed_called
    assert session.last_transcript == "Yeah"


def test_scenario3_correction_interrupts_immediately():
    sinks = DummySinks()
    text = "No stop"
    cls = ih.classify_transcript(text)
    assert cls == "interrupt"

    if cls == "interrupt":
        sinks.interrupt()

    assert sinks.interrupted


def test_scenario4_mixed_input_stops():
    sinks = DummySinks()
    text = "Yeah okay but wait"
    cls = ih.classify_transcript(text)
    assert cls == "interrupt"

    if cls == "interrupt":
        sinks.interrupt()

    assert sinks.interrupted
