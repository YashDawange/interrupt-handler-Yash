# tests/test_interrupt_handler.py
"""
Unit tests for InterruptHandler.

Tests cover:
- VAD while silent (should route immediately)
- Soft backchannel ignored while speaking
- Hard interrupt handled
- Mixed utterance interrupts
- Edge cases (empty transcripts, multiple soft words, etc.)
"""
import time
import pytest
from livekit.agents.voice.interrupt_handler import InterruptHandler


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


def test_soft_words_final_transcript(mock_audio, handler_config):
    """Test that soft words in final transcript are ignored."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()
    
    time.sleep(0.02)
    handler.on_stt_final("ok", 0.95)
    
    time.sleep(0.01)  # Small delay for processing
    
    assert len(interrupts) == 0, "Soft words in final transcript should not interrupt"
    assert mock_audio.is_playing(), "Audio should resume"


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


def test_hard_interrupt_final(mock_audio, handler_config):
    """Test that hard interrupt words in final transcript trigger interrupt."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()
    
    time.sleep(0.02)
    handler.on_stt_final("wait", 0.95)
    
    time.sleep(0.01)
    
    assert len(interrupts) >= 1, "Hard word in final should trigger interrupt"
    assert "wait" in interrupts[0].lower()


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


def test_multiple_soft_words(mock_audio, handler_config):
    """Test that multiple soft words together are still ignored."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()
    
    time.sleep(0.02)
    handler.on_stt_final("yeah ok hmm", 0.9)
    
    time.sleep(0.01)
    
    assert len(interrupts) == 0, "Multiple soft words should not interrupt"
    assert mock_audio.is_playing(), "Audio should resume"


def test_empty_transcript_resumes(mock_audio, handler_config):
    """Test that empty transcript resumes playback."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()
    
    time.sleep(0.02)
    handler.on_stt_final("", 0.0)
    
    time.sleep(0.01)
    
    assert len(interrupts) == 0, "Empty transcript should not interrupt"
    assert mock_audio.is_playing(), "Audio should resume on empty transcript"


def test_other_words_interrupt(mock_audio, handler_config):
    """Test that non-soft, non-hard words trigger interrupt."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()
    
    time.sleep(0.02)
    handler.on_stt_final("hello", 0.9)
    
    time.sleep(0.01)
    
    assert len(interrupts) >= 1, "Other words should trigger interrupt"
    assert "hello" in interrupts[0].lower()


def test_vad_ignored_during_confirmation_window(mock_audio, handler_config):
    """Test that VAD events are ignored during active confirmation window."""
    handler = InterruptHandler(mock_audio, config=handler_config)
    immediate_calls = []
    
    handler.on_immediate_user_speech = lambda: immediate_calls.append(1)
    handler.on_vad()  # Start confirmation window
    
    # Try to trigger VAD again during window
    handler.on_vad()
    
    assert len(immediate_calls) == 0, "VAD should be ignored during confirmation window"


def test_custom_soft_hard_words(mock_audio):
    """Test that custom soft/hard word lists work."""
    handler = InterruptHandler(
        mock_audio,
        config={
            "soft_words": ["custom_soft"],
            "hard_words": ["custom_hard"],
            "stt_confirm_ms": 50,
        }
    )
    interrupts = []
    
    handler.on_interrupt = lambda t: interrupts.append(t)
    handler.on_vad()
    
    time.sleep(0.02)
    handler.on_stt_final("custom_soft", 0.9)
    time.sleep(0.01)
    
    assert len(interrupts) == 0, "Custom soft word should not interrupt"
    
    handler.on_vad()
    time.sleep(0.02)
    handler.on_stt_final("custom_hard", 0.9)
    time.sleep(0.01)
    
    assert len(interrupts) >= 1, "Custom hard word should interrupt"
