#!/usr/bin/env python3
"""
Demo runner for InterruptHandler.

Simulates four scenarios:
1. VAD while agent is silent (immediate routing)
2. Soft backchannel words while agent is speaking (ignored)
3. Hard interrupt words while agent is speaking (interrupts)
4. Mixed utterance while agent is speaking (interrupts)
"""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from livekit.agents.voice.interrupt_handler import InterruptHandler


class MockAudioPlayer:
    """Mock audio player for demo."""
    
    def __init__(self):
        self._playing = False
        self._paused = False
        self._stopped = False
    
    def is_playing(self):
        return self._playing and not self._stopped
    
    def pause(self):
        self._paused = True
        self._playing = False
        print("  [AUDIO] Paused")
    
    def resume(self):
        self._paused = False
        self._playing = True
        print("  [AUDIO] Resumed")
    
    def stop(self):
        self._stopped = True
        self._playing = False
        print("  [AUDIO] Stopped")
    
    def start_playing(self):
        """Simulate agent starting to speak."""
        self._playing = True
        self._stopped = False
        self._paused = False
        print("  [AUDIO] Agent started speaking")


def print_scenario_header(num, title):
    """Print a formatted scenario header."""
    print("\n" + "=" * 70)
    print(f"SCENARIO {num}: {title}")
    print("=" * 70)


def scenario_1_immediate_routing():
    """Scenario 1: VAD while agent is silent."""
    print_scenario_header(1, "VAD While Agent is Silent (Immediate Routing)")
    
    audio = MockAudioPlayer()
    handler = InterruptHandler(audio, config={"stt_confirm_ms": 150, "debug": True})
    
    immediate_called = []
    handler.on_immediate_user_speech = lambda: immediate_called.append(True)
    
    print("\n[SETUP] Agent is silent (not playing)")
    print("[ACTION] VAD detects user speech...")
    
    handler.on_vad()
    
    time.sleep(0.1)
    
    print(f"\n[RESULT] on_immediate_user_speech called: {len(immediate_called) > 0}")
    assert len(immediate_called) > 0, "Should route immediately when agent is silent"
    print("✓ PASS: User speech routed immediately")


def scenario_2_soft_backchannel():
    """Scenario 2: Soft backchannel words ignored."""
    print_scenario_header(2, "Soft Backchannel Words (Ignored)")
    
    audio = MockAudioPlayer()
    audio.start_playing()
    handler = InterruptHandler(audio, config={"stt_confirm_ms": 150, "debug": True})
    
    interrupts = []
    handler.on_interrupt = lambda t: interrupts.append(t)
    
    print("\n[SETUP] Agent is speaking")
    print("[ACTION] User says 'yeah' (backchannel)...")
    
    handler.on_vad()
    time.sleep(0.05)
    handler.on_stt_partial("yeah", 0.9)
    time.sleep(0.1)
    handler.on_stt_final("yeah", 0.95)
    
    time.sleep(0.1)
    
    print(f"\n[RESULT] Interrupts triggered: {len(interrupts)}")
    print(f"[RESULT] Audio still playing: {audio.is_playing()}")
    assert len(interrupts) == 0, "Soft words should not interrupt"
    assert audio.is_playing(), "Audio should resume"
    print("✓ PASS: Soft backchannel words ignored, audio resumed")


def scenario_3_hard_interrupt():
    """Scenario 3: Hard interrupt words trigger stop."""
    print_scenario_header(3, "Hard Interrupt Words (Interrupts)")
    
    audio = MockAudioPlayer()
    audio.start_playing()
    handler = InterruptHandler(audio, config={"stt_confirm_ms": 150, "debug": True})
    
    interrupts = []
    handler.on_interrupt = lambda t: interrupts.append(t)
    
    print("\n[SETUP] Agent is speaking")
    print("[ACTION] User says 'stop' (hard interrupt)...")
    
    handler.on_vad()
    time.sleep(0.05)
    handler.on_stt_partial("stop", 0.95)
    
    time.sleep(0.1)
    
    print(f"\n[RESULT] Interrupts triggered: {len(interrupts)}")
    print(f"[RESULT] Interrupt text: {interrupts[0] if interrupts else 'None'}")
    print(f"[RESULT] Audio stopped: {audio._stopped}")
    assert len(interrupts) >= 1, "Hard word should trigger interrupt"
    assert "stop" in interrupts[0].lower(), "Interrupt should contain 'stop'"
    assert audio._stopped, "Audio should be stopped"
    print("✓ PASS: Hard interrupt word triggered stop")


def scenario_4_mixed_utterance():
    """Scenario 4: Mixed utterance triggers interrupt."""
    print_scenario_header(4, "Mixed Utterance (Interrupts)")
    
    audio = MockAudioPlayer()
    audio.start_playing()
    handler = InterruptHandler(audio, config={"stt_confirm_ms": 150, "debug": True})
    
    interrupts = []
    handler.on_interrupt = lambda t: interrupts.append(t)
    
    print("\n[SETUP] Agent is speaking")
    print("[ACTION] User says 'yeah wait' (mixed: soft + hard)...")
    
    handler.on_vad()
    time.sleep(0.05)
    handler.on_stt_partial("yeah wait", 0.9)
    
    time.sleep(0.1)
    
    print(f"\n[RESULT] Interrupts triggered: {len(interrupts)}")
    print(f"[RESULT] Interrupt text: {interrupts[0] if interrupts else 'None'}")
    print(f"[RESULT] Audio stopped: {audio._stopped}")
    assert len(interrupts) >= 1, "Mixed utterance with hard word should interrupt"
    assert audio._stopped, "Audio should be stopped"
    print("✓ PASS: Mixed utterance triggered interrupt")


def main():
    """Run all demo scenarios."""
    print("\n" + "=" * 70)
    print("INTERRUPT HANDLER DEMO")
    print("=" * 70)
    print("\nThis demo simulates four scenarios to demonstrate the")
    print("InterruptHandler's ability to distinguish between backchannel")
    print("words and real interrupts.\n")
    
    try:
        scenario_1_immediate_routing()
        time.sleep(0.5)
        
        scenario_2_soft_backchannel()
        time.sleep(0.5)
        
        scenario_3_hard_interrupt()
        time.sleep(0.5)
        
        scenario_4_mixed_utterance()
        
        print("\n" + "=" * 70)
        print("ALL SCENARIOS PASSED ✓")
        print("=" * 70)
        print("\nThe InterruptHandler successfully:")
        print("  • Routes user speech immediately when agent is silent")
        print("  • Ignores soft backchannel words while agent is speaking")
        print("  • Interrupts on hard interrupt words")
        print("  • Interrupts on mixed utterances containing hard words")
        print()
        
    except AssertionError as e:
        print(f"\n✗ FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

