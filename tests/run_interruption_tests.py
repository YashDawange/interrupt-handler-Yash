#!/usr/bin/env python3
"""
Simple test runner for interruption handler tests.

Can be run directly without pytest if needed:
    python3 tests/run_interruption_tests.py
"""

import sys
from pathlib import Path

# Add examples directory to path
examples_path = Path(__file__).parent.parent / "examples" / "voice_agents"
sys.path.insert(0, str(examples_path))

from interruption_handler_agent import InterruptionHandler


def test_basic_functionality():
    """Test basic handler functionality."""
    print("Testing basic functionality...")
    handler = InterruptionHandler()
    
    assert handler._backchanneling_words is not None
    assert handler._interruption_words is not None
    print("✓ Basic initialization works")


def test_backchanneling_detection():
    """Test backchanneling detection."""
    print("\nTesting backchanneling detection...")
    handler = InterruptionHandler()
    
    # Should detect backchanneling
    backchanneling_cases = [
        "yeah", "ok", "okay", "hmm", "uh-huh", "right", "sure",
        "okey", "oki", "kk",  # STT variations
        "okay,", "yeah.", "hmm...",  # With punctuation
        "yeah okay", "okay yeah",  # Multiple words
    ]
    
    for case in backchanneling_cases:
        result = handler.is_backchanneling(case)
        assert result is True, f"'{case}' should be detected as backchanneling"
        print(f"  ✓ '{case}' detected as backchanneling")
    
    # Should NOT detect as backchanneling
    non_backchanneling = [
        "hello", "what is that", "tell me more", "yeah wait", "okay stop"
    ]
    
    for case in non_backchanneling:
        result = handler.is_backchanneling(case)
        assert result is False, f"'{case}' should NOT be detected as backchanneling"
        print(f"  ✓ '{case}' correctly NOT detected as backchanneling")


def test_interruption_words():
    """Test interruption word detection."""
    print("\nTesting interruption word detection...")
    handler = InterruptionHandler()
    
    interruption_cases = [
        "wait", "stop", "no", "halt", "pause",
        "yeah wait", "okay stop", "hmm no",  # Mixed with backchanneling
    ]
    
    for case in interruption_cases:
        normalized = handler._normalize_text(case)
        result = handler._contains_interruption_word(normalized)
        assert result is True, f"'{case}' should contain interruption word"
        print(f"  ✓ '{case}' contains interruption word")


def test_scenarios():
    """Test the four main scenarios from the assignment."""
    print("\nTesting assignment scenarios...")
    handler = InterruptionHandler()
    
    # Scenario 1: Long explanation - backchanneling should be ignored
    handler.update_agent_state("speaking")
    assert handler.is_backchanneling("okay") is True
    assert handler.is_backchanneling("yeah") is True
    assert handler.is_backchanneling("uh-huh") is True
    print("  ✓ Scenario 1: Backchanneling detected while speaking")
    
    # Scenario 2: Passive affirmation - should be detectable
    handler.update_agent_state("listening")
    assert handler.is_backchanneling("yeah") is True
    print("  ✓ Scenario 2: Backchanneling detectable when listening")
    
    # Scenario 3: Correction - should interrupt
    handler.update_agent_state("speaking")
    normalized = handler._normalize_text("no stop")
    assert handler._contains_interruption_word(normalized) is True
    assert handler.is_backchanneling("no stop") is False
    print("  ✓ Scenario 3: Interruption words detected")
    
    # Scenario 4: Mixed input - should interrupt
    normalized = handler._normalize_text("yeah okay but wait")
    assert handler._contains_interruption_word(normalized) is True
    assert handler.is_backchanneling("yeah okay but wait") is False
    print("  ✓ Scenario 4: Mixed input with interruption word detected")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Interruption Handler Test Suite")
    print("=" * 60)
    
    try:
        test_basic_functionality()
        test_backchanneling_detection()
        test_interruption_words()
        test_scenarios()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

