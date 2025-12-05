"""
Comprehensive Test Suite for Smart Interruption Agent
=====================================================

This test suite validates all four evaluation scenarios and edge cases.

Run with: python test_agent.py
"""

import asyncio
import logging
from typing import List, Tuple
from smart_agent import InterruptionFilter, InterruptionConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class TestResults:
    """Track test results."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests: List[Tuple[str, bool, str]] = []
    
    def add(self, name: str, passed: bool, message: str = ""):
        self.tests.append((name, passed, message))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_summary(self):
        print("\n" + "="*70)
        print("TEST RESULTS SUMMARY")
        print("="*70)
        
        for name, passed, message in self.tests:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} - {name}")
            if message and not passed:
                print(f"        {message}")
        
        print("\n" + "="*70)
        total = self.passed + self.failed
        print(f"Total: {total} tests")
        print(f"Passed: {self.passed} ({100*self.passed/total:.1f}%)")
        print(f"Failed: {self.failed} ({100*self.failed/total:.1f}%)")
        print("="*70)
        
        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED! 🎉\n")
            return True
        else:
            print(f"\n❌ {self.failed} test(s) failed\n")
            return False


async def test_scenario_1_long_explanation(results: TestResults):
    """
    SCENARIO 1: The Long Explanation
    
    Context: Agent is reading a long paragraph about history.
    User Action: User says "Okay... yeah... uh-huh" while Agent is talking.
    Expected Result: Agent audio does not break. It ignores the user input completely.
    
    Evaluation: STRICT - Agent MUST continue without stopping, pausing, or hiccupping.
    """
    print("\n" + "="*70)
    print("SCENARIO 1: Long Explanation")
    print("="*70)
    print("Context: Agent is speaking a long paragraph")
    print("User says: 'Okay... yeah... uh-huh'")
    print("Expected: Agent continues WITHOUT stopping\n")
    
    config = InterruptionConfig()
    filter = InterruptionFilter(config)
    
    # Agent is speaking
    filter.set_agent_speaking(True)
    
    test_inputs = ["okay", "yeah", "uh-huh", "hmm", "right", "mhmm"]
    all_passed = True
    
    for input_text in test_inputs:
        should_suppress = filter.should_suppress(input_text, confidence=0.95)
        
        if should_suppress:
            print(f"  ✅ '{input_text}' -> SUPPRESSED (agent continues)")
        else:
            print(f"  ❌ '{input_text}' -> NOT SUPPRESSED (agent would stop!)")
            all_passed = False
        
        results.add(
            f"Scenario 1 - '{input_text}' during speech",
            should_suppress,
            f"Expected suppression for filler word '{input_text}' during speech"
        )
    
    if all_passed:
        print("\n✅ SCENARIO 1 PASSED - Agent continues over all filler words")
    else:
        print("\n❌ SCENARIO 1 FAILED - Agent would stop on filler words")


async def test_scenario_2_passive_affirmation(results: TestResults):
    """
    SCENARIO 2: The Passive Affirmation
    
    Context: Agent asks "Are you ready?" and goes silent.
    User Action: User says "Yeah."
    Expected Result: Agent processes "Yeah" as an answer and proceeds.
    
    Evaluation: Agent must respond to input when silent (state awareness).
    """
    print("\n" + "="*70)
    print("SCENARIO 2: Passive Affirmation")
    print("="*70)
    print("Context: Agent asks 'Are you ready?' and goes SILENT")
    print("User says: 'Yeah'")
    print("Expected: Agent processes 'Yeah' and responds\n")
    
    config = InterruptionConfig()
    filter = InterruptionFilter(config)
    
    # Agent is SILENT
    filter.set_agent_speaking(False)
    
    test_inputs = ["yeah", "ok", "yes", "sure", "yep"]
    all_passed = True
    
    for input_text in test_inputs:
        should_suppress = filter.should_suppress(input_text, confidence=0.95)
        
        # When agent is silent, should NOT suppress (should process input)
        if not should_suppress:
            print(f"  ✅ '{input_text}' -> NOT SUPPRESSED (agent will respond)")
        else:
            print(f"  ❌ '{input_text}' -> SUPPRESSED (agent would ignore!)")
            all_passed = False
        
        results.add(
            f"Scenario 2 - '{input_text}' when silent",
            not should_suppress,
            f"Expected to process '{input_text}' when agent is silent"
        )
    
    if all_passed:
        print("\n✅ SCENARIO 2 PASSED - Agent responds when silent")
    else:
        print("\n❌ SCENARIO 2 FAILED - Agent ignores input when silent")


async def test_scenario_3_correction(results: TestResults):
    """
    SCENARIO 3: The Correction
    
    Context: Agent is counting "One, two, three..."
    User Action: User says "No stop."
    Expected Result: Agent cuts off immediately.
    
    Evaluation: Agent must stop for command words even while speaking.
    """
    print("\n" + "="*70)
    print("SCENARIO 3: Correction")
    print("="*70)
    print("Context: Agent is counting 'One, two, three...'")
    print("User says: 'No stop'")
    print("Expected: Agent stops immediately\n")
    
    config = InterruptionConfig()
    filter = InterruptionFilter(config)
    
    # Agent is speaking
    filter.set_agent_speaking(True)
    
    test_inputs = [
        ("no stop", True),
        ("wait", True),
        ("stop", True),
        ("hold on", True),
        ("pause", True),
        ("no", True),
    ]
    all_passed = True
    
    for input_text, _ in test_inputs:
        should_suppress = filter.should_suppress(input_text, confidence=0.95)
        
        # Should NOT suppress command words
        if not should_suppress:
            print(f"  ✅ '{input_text}' -> NOT SUPPRESSED (agent stops)")
        else:
            print(f"  ❌ '{input_text}' -> SUPPRESSED (agent would continue!)")
            all_passed = False
        
        results.add(
            f"Scenario 3 - '{input_text}' during speech",
            not should_suppress,
            f"Expected interruption for command '{input_text}'"
        )
    
    if all_passed:
        print("\n✅ SCENARIO 3 PASSED - Agent stops for commands")
    else:
        print("\n❌ SCENARIO 3 FAILED - Agent doesn't stop for commands")


async def test_scenario_4_mixed_input(results: TestResults):
    """
    SCENARIO 4: The Mixed Input
    
    Context: Agent is speaking.
    User Action: User says "Yeah okay but wait."
    Expected Result: Agent stops (because "but wait" is not in the ignore list).
    
    Evaluation: Agent must detect command words in mixed sentences.
    """
    print("\n" + "="*70)
    print("SCENARIO 4: Mixed Input")
    print("="*70)
    print("Context: Agent is speaking")
    print("User says: 'Yeah okay but wait'")
    print("Expected: Agent stops (contains command words)\n")
    
    config = InterruptionConfig()
    filter = InterruptionFilter(config)
    
    # Agent is speaking
    filter.set_agent_speaking(True)
    
    test_inputs = [
        ("yeah okay but wait", False, "contains 'but' and 'wait'"),
        ("hmm but actually", False, "contains 'but' and 'actually'"),
        ("ok wait a second", False, "contains 'wait'"),
        ("yeah no", False, "contains 'no'"),
        ("right however", False, "contains 'however'"),
        ("yeah okay right", True, "only filler words"),
    ]
    all_passed = True
    
    for input_text, should_be_suppressed, reason in test_inputs:
        should_suppress = filter.should_suppress(input_text, confidence=0.95)
        
        if should_suppress == should_be_suppressed:
            status = "SUPPRESSED" if should_suppress else "NOT SUPPRESSED"
            print(f"  ✅ '{input_text}' -> {status} ({reason})")
        else:
            expected_status = "SUPPRESSED" if should_be_suppressed else "NOT SUPPRESSED"
            actual_status = "SUPPRESSED" if should_suppress else "NOT SUPPRESSED"
            print(f"  ❌ '{input_text}' -> {actual_status} (expected {expected_status})")
            all_passed = False
        
        results.add(
            f"Scenario 4 - '{input_text}'",
            should_suppress == should_be_suppressed,
            f"Expected {expected_status} for '{input_text}' ({reason})"
        )
    
    if all_passed:
        print("\n✅ SCENARIO 4 PASSED - Agent detects commands in mixed input")
    else:
        print("\n❌ SCENARIO 4 FAILED - Agent misclassifies mixed input")


async def test_edge_cases(results: TestResults):
    """Test additional edge cases."""
    print("\n" + "="*70)
    print("EDGE CASES")
    print("="*70)
    
    config = InterruptionConfig()
    filter = InterruptionFilter(config)
    
    # Test 1: Empty input
    filter.set_agent_speaking(True)
    result = filter.should_suppress("", confidence=0.95)
    results.add(
        "Edge case - Empty input",
        result == True,  # Empty is treated as filler
        "Empty input should be suppressed during speech"
    )
    print(f"  {'✅' if result else '❌'} Empty input -> {'SUPPRESSED' if result else 'NOT SUPPRESSED'}")
    
    # Test 2: Low confidence
    result = filter.should_suppress("yeah", confidence=0.3)
    results.add(
        "Edge case - Low confidence",
        result == False,  # Low confidence = don't suppress (be safe)
        "Low confidence should not suppress (be conservative)"
    )
    print(f"  {'✅' if not result else '❌'} Low confidence -> {'NOT SUPPRESSED' if not result else 'SUPPRESSED'}")
    
    # Test 3: Punctuation handling
    result = filter.should_suppress("yeah, ok!", confidence=0.95)
    results.add(
        "Edge case - Punctuation",
        result == True,
        "Punctuation should be normalized"
    )
    print(f"  {'✅' if result else '❌'} 'yeah, ok!' -> {'SUPPRESSED' if result else 'NOT SUPPRESSED'}")
    
    # Test 4: Case sensitivity
    result = filter.should_suppress("YEAH OK", confidence=0.95)
    results.add(
        "Edge case - Case sensitivity",
        result == True,
        "Input should be case-insensitive"
    )
    print(f"  {'✅' if result else '❌'} 'YEAH OK' -> {'SUPPRESSED' if result else 'NOT SUPPRESSED'}")
    
    # Test 5: Multiple command words
    filter.set_agent_speaking(True)
    result = filter.should_suppress("wait no stop", confidence=0.95)
    results.add(
        "Edge case - Multiple commands",
        result == False,
        "Multiple command words should trigger interruption"
    )
    print(f"  {'✅' if not result else '❌'} 'wait no stop' -> {'NOT SUPPRESSED' if not result else 'SUPPRESSED'}")
    
    print("\n✅ Edge cases tested")


async def test_configuration(results: TestResults):
    """Test configuration flexibility."""
    print("\n" + "="*70)
    print("CONFIGURATION TESTS")
    print("="*70)
    
    # Test custom configuration
    custom_config = InterruptionConfig(
        filler_words={'roger', 'copy', '10-4'},
        command_words={'break', 'over'},
        stt_wait_timeout=0.20,
        min_confidence=0.7
    )
    
    filter = InterruptionFilter(custom_config)
    filter.set_agent_speaking(True)
    
    # Test custom filler
    result = filter.should_suppress("roger", confidence=0.95)
    results.add(
        "Config - Custom filler word",
        result == True,
        "Custom filler word 'roger' should be suppressed"
    )
    print(f"  {'✅' if result else '❌'} Custom filler 'roger' -> {'SUPPRESSED' if result else 'NOT SUPPRESSED'}")
    
    # Test custom command
    result = filter.should_suppress("break", confidence=0.95)
    results.add(
        "Config - Custom command word",
        result == False,
        "Custom command word 'break' should interrupt"
    )
    print(f"  {'✅' if not result else '❌'} Custom command 'break' -> {'NOT SUPPRESSED' if not result else 'SUPPRESSED'}")
    
    # Test that old words don't work
    result = filter.should_suppress("yeah", confidence=0.95)
    results.add(
        "Config - Override default",
        result == False,  # 'yeah' not in custom config, so treated as regular input
        "Default word 'yeah' should not be in custom config"
    )
    print(f"  {'✅' if not result else '❌'} Default 'yeah' (not in custom) -> {'NOT SUPPRESSED' if not result else 'SUPPRESSED'}")
    
    print("\n✅ Configuration flexibility verified")


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("SMART INTERRUPTION AGENT - COMPREHENSIVE TEST SUITE")
    print("="*70)
    print("\nTesting all evaluation scenarios and edge cases...\n")
    
    results = TestResults()
    
    # Run all test scenarios
    await test_scenario_1_long_explanation(results)
    await test_scenario_2_passive_affirmation(results)
    await test_scenario_3_correction(results)
    await test_scenario_4_mixed_input(results)
    await test_edge_cases(results)
    await test_configuration(results)
    
    # Print summary
    all_passed = results.print_summary()
    
    # Exit code
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
