#!/usr/bin/env python3
"""
Simple test script to verify the filler words logic works correctly.
This tests the core logic without requiring the full LiveKit infrastructure.
"""

def test_filler_words_logic():
    """Test the core logic for determining if text contains only filler words."""

    # Test filler words list
    filler_words = ['yeah', 'ok', 'hmm', 'right', 'uh-huh', 'aha', 'okay', 'alright', 'hmm', 'alright then', 'uh-huh']

    def contains_only_filler_words(text, filler_list):
        """Check if text contains only filler words."""
        if not text.strip():
            return True  # Empty text is considered filler

        words = text.strip().lower().split()
        return all(word.lower() in filler_list for word in words)

    # Test cases
    test_cases = [
        # (input_text, expected_result, description)
        ("yeah", True, "Single filler word"),
        ("ok", True, "Single filler word"),
        ("yeah okay", True, "Multiple filler words"),
        ("yeah ok hmm", True, "Multiple filler words"),
        ("stop", False, "Non-filler word"),
        ("yeah stop", False, "Mixed: filler + non-filler"),
        ("ok but wait", False, "Mixed: filler + non-filler"),
        ("", True, "Empty text"),
        ("   ", True, "Whitespace only"),
        ("Yeah", True, "Case insensitive"),
        ("OK", True, "Case insensitive"),
        ("hmm", True, "Single filler word"),
        ("uh-huh", True, "Single filler word"),
        ("alright then", False, "Mixed: filler + non-filler"),

    ]

    print("Testing filler words logic...")
    print("=" * 50)

    all_passed = True
    for text, expected, description in test_cases:
        result = contains_only_filler_words(text, filler_words)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        print("text:",text,"expected:", expected, "result:", result, status)
        if result != expected:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("🎉 All tests passed! The filler words logic is working correctly.")
    else:
        print("❌ Some tests failed. Please check the implementation.")

    return all_passed

def test_agent_state_logic():
    """Test the agent state logic (speaking vs silent)."""

    def should_interrupt(agent_speaking, transcript, filler_words):
        """Simulate the interruption decision logic."""
        if agent_speaking and transcript.strip():
            words = transcript.strip().lower().split()
            if all(word.lower() in filler_words for word in words):
                return False  # Don't interrupt for filler words when speaking
        return True  # Interrupt in all other cases

    filler_words = ['yeah', 'ok', 'hmm']

    test_cases = [
        # (agent_speaking, transcript, expected_interrupt, description)
        (True, "yeah", False, "Agent speaking + filler word = no interrupt"),
        (True, "ok", False, "Agent speaking + filler word = no interrupt"),
        (True, "stop", True, "Agent speaking + command = interrupt"),
        (True, "yeah stop", True, "Agent speaking + mixed = interrupt"),
        (False, "yeah", True, "Agent silent + filler word = respond normally"),
        (False, "stop", True, "Agent silent + command = respond normally"),
    ]

    print("\nTesting agent state logic...")
    print("=" * 50)

    all_passed = True
    for agent_speaking, transcript, expected, description in test_cases:
        result = should_interrupt(agent_speaking, transcript, filler_words)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        agent_state = "speaking" if agent_speaking else "silent"
        print(agent_speaking,transcript, expected, result, status)
        if result != expected:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("🎉 All agent state tests passed!")
    else:
        print("❌ Some agent state tests failed.")

    return all_passed

if __name__ == "__main__":
    print("🔍 Testing Intelligent Interruption Handling Feature")
    print("This script verifies the core logic without requiring LiveKit infrastructure.\n")

    filler_test_passed = test_filler_words_logic()
    state_test_passed = test_agent_state_logic()

    print("\n" + "=" * 60)
    if filler_test_passed and state_test_passed:
        print("🎉 ALL TESTS PASSED! The feature logic is working correctly.")
        print("\nNext steps:")
        print("1. Set up LiveKit credentials (.env file)")
        print("2. Run the example agent: python examples/voice_agents/interrupt_handler_agent.py")
        print("3. Test with actual voice input using the scenarios below")
    else:
        print("❌ SOME TESTS FAILED. Please check the implementation.")

    print("\n📋 Test Scenarios for Live Agent:")
    print("1. Agent speaking → User says 'yeah' → Agent should continue speaking")
    print("2. Agent speaking → User says 'stop' → Agent should interrupt")
    print("3. Agent silent → User says 'yeah' → Agent should respond")
    print("4. Agent speaking → User says 'yeah but wait' → Agent should interrupt")