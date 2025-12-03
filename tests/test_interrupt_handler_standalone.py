# tests/test_interrupt_handler_standalone.py
"""
Standalone unit tests for InterruptHandler (doesn't require conftest or package installation).

This version can be run without the full package installation:
python -m pytest tests/test_interrupt_handler_standalone.py -v
"""
import sys
import time
import importlib.util
from pathlib import Path

# Import interrupt_handler module directly to avoid package initialization dependencies
project_root = Path(__file__).parent.parent
interrupt_handler_path = project_root / "livekit-agents" / "livekit" / "agents" / "voice" / "interrupt_handler.py"

spec = importlib.util.spec_from_file_location("interrupt_handler", interrupt_handler_path)
interrupt_handler_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interrupt_handler_module)
InterruptHandler = interrupt_handler_module.InterruptHandler

import pytest


class MockAudio:
    """Mock audio player for testing."""
    
    def __init__(self):
        self.playing = True
        self.paused = False
        self.stopped = False
    
    def is_playing(self):
        return self.playing and not self.stopped
    
    def pause(self):
        self.paused = True
        self.playing = False
    
    def resume(self):
        self.paused = False
        self.playing = True
    
    def stop(self):
        self.stopped = True
        self.playing = False


@pytest.fixture
def mock_audio():
    """Fixture providing a fresh MockAudio instance."""
    return MockAudio()


@pytest.fixture
def handler_config():
    """Fixture providing test configuration."""
    return {"stt_confirm_ms": 50, "debug": False}


def test_vad_while_silent_routes_immediately(mock_audio, handler_config):
    """Test that VAD while agent is silent routes immediately."""
    mock_audio.playing = False
    handler = InterruptHandler(mock_audio, config=handler_config)
    calls = {"immediate": 0}
    
    def on_immediate():
        calls["immediate"] += 1
    
    handler.on_immediate_user_speech = on_immediate
    handler.on_vad()
    
    assert calls["immediate"] == 1, "on_immediate_user_speech should be called once"


def test_soft_ignored_while_speaking(mock_audio, handler_config):
    """Test that soft backchannel words are ignored while agent is speaking."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()  # Start confirmation window
    
    time.sleep(0.02)  # Small delay to simulate STT processing
    handler.on_stt_partial("yeah", 0.9)
    
    # Wait for confirmation window to complete
    time.sleep(0.18)
    
    assert len(interrupts) == 0, "Soft words should not trigger interrupt"
    assert mock_audio.is_playing(), "Audio should resume after soft words"


def test_hard_interrupt_partial(mock_audio, handler_config):
    """Test that hard interrupt words in partial transcript trigger immediate interrupt."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()
    
    time.sleep(0.02)
    handler.on_stt_partial("stop", 0.95)
    
    time.sleep(0.01)  # Small delay for processing
    
    assert len(interrupts) >= 1, "Hard word should trigger interrupt"
    assert "stop" in interrupts[0].lower(), "Interrupt should contain the hard word"
    assert mock_audio.stopped, "Audio should be stopped"


def test_mixed_interrupts(mock_audio, handler_config):
    """Test that mixed utterances (soft + hard words) trigger interrupt."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()
    
    time.sleep(0.02)
    handler.on_stt_partial("yeah wait", 0.9)
    
    time.sleep(0.01)
    
    assert len(interrupts) >= 1, "Mixed utterance with hard word should interrupt"
    assert mock_audio.stopped, "Audio should be stopped"

