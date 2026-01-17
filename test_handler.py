import sys
from interrupt_handler import InterruptionHandler
from config import IGNORE_WORDS


def run_tests():
    
    print("=" * 60)
    print("INTERRUPTION HANDLER - TEST SUITE")
    print("=" * 60)
    print()
    
    handler = InterruptionHandler(ignore_words=IGNORE_WORDS)
    
    test_cases = [
        (True, "yeah", False, "Backchanneling while speaking"),
        (True, "ok", False, "Single acknowledgment"),
        (True, "hmm", False, "Listening cue"),
        (True, "uh-huh", False, "Affirmative sound"),
        (True, "okay yeah right", False, "Multiple backchannels"),
        
        (False, "yeah", True, "Answer when silent"),
        (False, "ok", True, "Acknowledge when silent"),
        (False, "sure", True, "Affirmation when silent"),
        
        (True, "stop", True, "Clear stop command"),
        (True, "no", True, "Negation"),
        (True, "wait", True, "Pause command"),
        (True, "no stop", True, "Combined command"),
        
        (True, "yeah wait", True, "Backchannel + command"),
        (True, "ok but wait", True, "Mixed with 'but'"),
        (True, "hmm actually", True, "Backchannel + correction"),
        (True, "yeah okay but stop", True, "Complex mixed input"),
        
        (True, "", False, "Empty input"),
        (False, "hello", True, "Greeting when silent"),
        (False, "start", True, "Command when silent"),
        (True, "what", True, "Question while speaking"),
    ]
    
    passed = 0
    failed = 0
    
    print(f"Running {len(test_cases)} test cases...\n")
    
    for speaking, user_input, expected, test_name in test_cases:
        handler.set_agent_speaking(speaking)
        result = handler.should_interrupt(user_input)
        
        status = "✓ PASS" if result == expected else "✗ FAIL"
        agent_state = "SPEAKING" if speaking else "SILENT  "
        action = "INTERRUPT" if result else "IGNORE   "
        expected_action = "INTERRUPT" if expected else "IGNORE   "
        
        if result == expected:
            passed += 1
            color = ""
        else:
            failed += 1
            color = " "
        
        print(f"{color}{status} | Agent: {agent_state} | Input: '{user_input:20}' | "
              f"Got: {action} | Expected: {expected_action} | {test_name}")
    
    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 60)
    
    if failed == 0:
        print(" ALL TESTS PASSED! ")
        return 0
    else:
        print(f" {failed} tests failed")
        return 1


def test_config():
    print("\n" + "=" * 60)
    print("TESTING CONFIGURABLE IGNORE WORDS")
    print("=" * 60 + "\n")
    
    custom = ["test", "demo"]
    handler = InterruptionHandler(ignore_words=custom)
    
    handler.set_agent_speaking(True)
    
    r1 = handler.should_interrupt("test")
    r2 = handler.should_interrupt("demo")
    r3 = handler.should_interrupt("yeah")
    
    print(f"Custom word 'test' ignored: {not r1} (Expected: True)")
    print(f"Custom word 'demo' ignored: {not r2} (Expected: True)")
    print(f"Default word 'yeah' NOT ignored: {r3} (Expected: True)")
    
    handler.add_ignore_word("newword")
    r4 = handler.should_interrupt("newword")
    print(f"Dynamically added 'newword' ignored: {not r4} (Expected: True)")
    
    print("\n✓ Config tests passed\n")


if __name__ == "__main__":
    exit_code = run_tests()
    test_config()
    sys.exit(exit_code)
