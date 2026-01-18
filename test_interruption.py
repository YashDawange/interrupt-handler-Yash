"""
Quick test script to verify interruption handler functionality.
Run this to verify the implementation works correctly.
"""

from livekit.agents.voice.interruption_handler import InterruptionHandler


def test_interruption_handler():
    """Test the interruption handler with various scenarios."""
    handler = InterruptionHandler()

    print("Testing Interruption Handler...")
    print("-" * 50)

    # Test 1: Should ignore "yeah" when agent is speaking
    result1 = handler.should_ignore_interruption("yeah", agent_is_speaking=True)
    assert result1 == True, "Should ignore 'yeah' when agent is speaking"
    print("✅ Test 1: Ignores 'yeah' when agent is speaking")

    # Test 2: Should NOT ignore "yeah" when agent is silent
    result2 = handler.should_ignore_interruption("yeah", agent_is_speaking=False)
    assert result2 == False, "Should NOT ignore 'yeah' when agent is silent"
    print("✅ Test 2: Responds to 'yeah' when agent is silent")

    # Test 3: Should NOT ignore "stop" when agent is speaking
    result3 = handler.should_ignore_interruption("stop", agent_is_speaking=True)
    assert result3 == False, "Should NOT ignore 'stop' when agent is speaking"
    print("✅ Test 3: Interrupts on 'stop' when agent is speaking")

    # Test 4: Should interrupt on mixed input
    result4 = handler.should_ignore_interruption("yeah wait", agent_is_speaking=True)
    assert result4 == False, "Should interrupt on mixed input with command"
    print("✅ Test 4: Interrupts on mixed input ('yeah wait')")

    # Test 5: Should ignore multiple backchanneling words
    result5 = handler.should_ignore_interruption("yeah ok hmm", agent_is_speaking=True)
    assert result5 == True, "Should ignore multiple backchanneling words"
    print("✅ Test 5: Ignores multiple backchanneling words")

    # Test 6: Should interrupt on "no"
    result6 = handler.should_ignore_interruption("no", agent_is_speaking=True)
    assert result6 == False, "Should interrupt on 'no'"
    print("✅ Test 6: Interrupts on 'no'")

    # Test 7: Should interrupt on "wait"
    result7 = handler.should_ignore_interruption("wait", agent_is_speaking=True)
    assert result7 == False, "Should interrupt on 'wait'"
    print("✅ Test 7: Interrupts on 'wait'")

    # Test 8: Check interrupt command detection
    assert handler.check_transcript_for_interrupt("yeah wait") == True
    assert handler.check_transcript_for_interrupt("just yeah") == False
    print("✅ Test 8: Interrupt command detection works")

    print("-" * 50)
    print("🎉 All tests passed! Implementation is working correctly.")


if __name__ == "__main__":
    test_interruption_handler()

