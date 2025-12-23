"""
Simple standalone test to verify InterruptionFilter functionality.
Run from the livekit-agents directory: python simple_test.py
"""

import sys
# sys.path.insert(0, 'livekit/agents/voice')

from livekit.agents.voice.interrupt_filter import InterruptionFilter

def test_interruption_filter():
    """Run basic tests on the InterruptionFilter."""
    
    print("Testing InterruptionFilter...\n")
    filter = InterruptionFilter()
    
    # Test 1: Backchannel ignored when agent speaking
    print("Test 1: Backchannel words while agent speaking")
    test_cases = ["yeah", "ok", "hmm", "right"]
    for word in test_cases:
        result = filter.should_ignore_transcript(word, agent_is_speaking=True)
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: '{word}' → ignored={result}")
    
    # Test 2: Backchannel processed when agent silent
    print("\nTest 2: Backchannel words while agent silent")
    for word in test_cases:
        result = filter.should_ignore_transcript(word, agent_is_speaking=False)
        status = "✓ PASS" if not result else "✗ FAIL"
        print(f"  {status}: '{word}' → ignored={result}")
    
    # Test 3: Interruption commands never ignored
    print("\nTest 3: Interruption commands")
    commands = ["wait", "stop", "no"]
    for cmd in commands:
        result = filter.should_ignore_transcript(cmd, agent_is_speaking=True)
        status = "✓ PASS" if not result else "✗ FAIL"
        print(f"  {status}: '{cmd}' → ignored={result}")
    
    # Test 4: Mixed input not ignored
    print("\nTest 4: Mixed input (backchannel + other words)")
    mixed = ["yeah but wait", "ok I have a question"]
    for phrase in mixed:
        result = filter.should_ignore_transcript(phrase, agent_is_speaking=True)
        status = "✓ PASS" if not result else "✗ FAIL"
        print(f"  {status}: '{phrase}' → ignored={result}")
    
    # Test 5: Filter reasons
    print("\nTest 5: Filter reasoning")
    test_scenarios = [
        ("yeah", True, "backchannel"),
        ("wait", True, "command"),
        ("hello", True, "mixed"),
    ]
    for transcript, speaking, expected in test_scenarios:
        reason = filter.get_filter_reason(transcript, speaking)
        print(f"  '{transcript}' (speaking={speaking}): {reason}")
    
    print("\nAll manual tests completed!")

if __name__ == "__main__":
    test_interruption_filter()
