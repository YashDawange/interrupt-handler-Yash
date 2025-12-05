"""Simple test runner for interruption filter (no pytest required)."""

import sys
sys.path.insert(0, 'livekit-agents')

from livekit.agents.voice.interruption_filter import InterruptionFilter


def test_backchannel_ignored_when_speaking():
    """Backchannel words should be ignored when agent is speaking."""
    filter = InterruptionFilter()
    
    tests = [
        ("yeah", False),
        ("ok", False),
        ("hmm", False),
        ("uh-huh", False),
        ("right", False),
        ("yeah ok", False),
        ("ok yeah hmm", False),
    ]
    
    for transcript, expected in tests:
        result = filter.should_interrupt(transcript, agent_is_speaking=True)
        status = "✓" if result == expected else "✗"
        print(f"{status} Backchannel '{transcript}': should_interrupt={result} (expected={expected})")
        if result != expected:
            return False
    return True


def test_command_words_interrupt():
    """Command words should always interrupt."""
    filter = InterruptionFilter()
    
    tests = [
        ("stop", True),
        ("wait", True),
        ("no", True),
        ("hold on", True),
        ("pause", True),
    ]
    
    for transcript, expected in tests:
        result = filter.should_interrupt(transcript, agent_is_speaking=True)
        status = "✓" if result == expected else "✗"
        print(f"{status} Command '{transcript}': should_interrupt={result} (expected={expected})")
        if result != expected:
            return False
    return True


def test_mixed_input_interrupts():
    """Mixed input (backchannel + command) should interrupt."""
    filter = InterruptionFilter()
    
    tests = [
        ("yeah wait", True),
        ("ok but", True),
        ("yeah wait a second", True),
        ("hmm actually", True),
    ]
    
    for transcript, expected in tests:
        result = filter.should_interrupt(transcript, agent_is_speaking=True)
        status = "✓" if result == expected else "✗"
        print(f"{status} Mixed '{transcript}': should_interrupt={result} (expected={expected})")
        if result != expected:
            return False
    return True


def test_agent_not_speaking():
    """When agent is not speaking, all input should be processed."""
    filter = InterruptionFilter()
    
    tests = [
        ("yeah", True),
        ("stop", True),
        ("hello there", True),
    ]
    
    for transcript, expected in tests:
        result = filter.should_interrupt(transcript, agent_is_speaking=False)
        status = "✓" if result == expected else "✗"
        print(f"{status} Agent silent '{transcript}': should_interrupt={result} (expected={expected})")
        if result != expected:
            return False
    return True


def test_other_input_interrupts():
    """Other input (not backchannel) should interrupt."""
    filter = InterruptionFilter()
    
    tests = [
        ("tell me more", True),
        ("what about", True),
        ("can you explain", True),
    ]
    
    for transcript, expected in tests:
        result = filter.should_interrupt(transcript, agent_is_speaking=True)
        status = "✓" if result == expected else "✗"
        print(f"{status} Other '{transcript}': should_interrupt={result} (expected={expected})")
        if result != expected:
            return False
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Intelligent Interruption Filter")
    print("=" * 60)
    
    tests = [
        ("Backchannel ignored when speaking", test_backchannel_ignored_when_speaking),
        ("Command words interrupt", test_command_words_interrupt),
        ("Mixed input interrupts", test_mixed_input_interrupts),
        ("Agent not speaking processes all", test_agent_not_speaking),
        ("Other input interrupts", test_other_input_interrupts),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n{name}:")
        try:
            if test_func():
                passed += 1
                print(f"  ✓ PASSED")
            else:
                failed += 1
                print(f"  ✗ FAILED")
        except Exception as e:
            failed += 1
            print(f"  ✗ FAILED with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
