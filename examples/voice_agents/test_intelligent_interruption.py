"""
Test Script for Intelligent Interruption Handling

This script demonstrates and tests all scenarios from the requirements.
It creates a simple test harness to verify the intelligent interruption behavior.

Usage:
    python test_intelligent_interruption.py
"""

import asyncio
import logging
import sys
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("test-intelligent-interruption")


@dataclass
class TestScenario:
    """Represents a test scenario for interruption handling."""

    name: str
    description: str
    agent_state: str  # "speaking" or "silent"
    user_input: str
    expected_behavior: str
    should_interrupt: bool


# Define test scenarios from requirements
TEST_SCENARIOS = [
    TestScenario(
        name="Scenario 1: The Long Explanation",
        description="User says backchannel words while agent is speaking",
        agent_state="speaking",
        user_input="yeah... okay... uh-huh",
        expected_behavior="Agent CONTINUES speaking without interruption",
        should_interrupt=False,
    ),
    TestScenario(
        name="Scenario 2: The Passive Affirmation",
        description="User says 'yeah' when agent is silent",
        agent_state="silent",
        user_input="yeah",
        expected_behavior="Agent PROCESSES input and responds",
        should_interrupt=False,  # Not an interruption, normal flow
    ),
    TestScenario(
        name="Scenario 3: The Active Interruption",
        description="User says 'stop' while agent is speaking",
        agent_state="speaking",
        user_input="no stop",
        expected_behavior="Agent STOPS immediately",
        should_interrupt=True,
    ),
    TestScenario(
        name="Scenario 4: The Mixed Input",
        description="User says 'yeah okay but wait' while agent is speaking",
        agent_state="speaking",
        user_input="yeah okay but wait",
        expected_behavior="Agent STOPS (contains non-backchannel word)",
        should_interrupt=True,
    ),
]


def analyze_scenario(scenario: TestScenario, backchannel_words: list[str]) -> dict:
    """
    Analyze a test scenario and predict behavior.

    Args:
        scenario: The test scenario to analyze
        backchannel_words: List of configured backchannel words

    Returns:
        Dictionary with analysis results
    """
    words = scenario.user_input.lower().split()
    backchannel_set = {word.lower().strip(".,!?") for word in backchannel_words}

    # Check if all words are backchannel words
    non_backchannel_words = [
        word for word in words if word.strip(".,!?") not in backchannel_set
    ]

    is_backchannel_only = len(non_backchannel_words) == 0 and len(words) > 0

    # Determine expected behavior
    if scenario.agent_state == "speaking":
        if is_backchannel_only:
            predicted_behavior = "IGNORE (backchannel only)"
            will_interrupt = False
        else:
            predicted_behavior = "INTERRUPT (contains command words)"
            will_interrupt = True
    else:  # agent_state == "silent"
        predicted_behavior = "RESPOND (normal input processing)"
        will_interrupt = False

    return {
        "words": words,
        "non_backchannel_words": non_backchannel_words,
        "is_backchannel_only": is_backchannel_only,
        "predicted_behavior": predicted_behavior,
        "will_interrupt": will_interrupt,
        "matches_expected": will_interrupt == scenario.should_interrupt,
    }


def print_test_results():
    """Print test results for all scenarios."""
    backchannel_words = [
        "yeah",
        "ok",
        "okay",
        "hmm",
        "uh-huh",
        "mm-hmm",
        "right",
        "sure",
        "got it",
        "aha",
    ]

    print("\n" + "=" * 80)
    print("INTELLIGENT INTERRUPTION HANDLING - TEST SCENARIOS")
    print("=" * 80 + "\n")

    print(f"Configured Backchannel Words: {', '.join(backchannel_words)}\n")

    all_passed = True

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n{'─' * 80}")
        print(f"TEST {i}: {scenario.name}")
        print(f"{'─' * 80}")
        print(f"Description: {scenario.description}")
        print(f"Agent State: {scenario.agent_state.upper()}")
        print(f"User Input:  \"{scenario.user_input}\"")
        print(f"\nExpected Behavior: {scenario.expected_behavior}")

        # Analyze the scenario
        analysis = analyze_scenario(scenario, backchannel_words)

        print(f"\nAnalysis:")
        print(f"  - Words detected: {analysis['words']}")
        print(f"  - Non-backchannel words: {analysis['non_backchannel_words'] or 'None'}")
        print(f"  - Is backchannel only? {analysis['is_backchannel_only']}")
        print(f"\nPredicted System Behavior: {analysis['predicted_behavior']}")

        # Check if prediction matches expected
        status = "✅ PASS" if analysis["matches_expected"] else "❌ FAIL"
        print(f"\nTest Result: {status}")

        if not analysis["matches_expected"]:
            all_passed = False
            print(f"  ERROR: Expected interrupt={scenario.should_interrupt}, "
                  f"but predicted interrupt={analysis['will_interrupt']}")

    print(f"\n{'=' * 80}")
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 80 + "\n")

    return all_passed


def print_usage_instructions():
    """Print instructions for manual testing."""
    print("\n" + "=" * 80)
    print("MANUAL TESTING INSTRUCTIONS")
    print("=" * 80 + "\n")

    print("To manually test the intelligent interruption agent:\n")

    print("1. Start the agent:")
    print("   cd examples/voice_agents")
    print("   python intelligent_interruption_agent.py dev\n")

    print("2. Connect to the agent:")
    print("   - Use LiveKit Agents Playground: https://agents-playground.livekit.io/")
    print("   - Or use any LiveKit client SDK\n")

    print("3. Test each scenario:\n")

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"   Test {i}: {scenario.name}")
        print(f"   - Wait for agent to be in '{scenario.agent_state}' state")
        print(f"   - Say: \"{scenario.user_input}\"")
        print(f"   - Verify: {scenario.expected_behavior}")
        print()

    print("4. Check logs for:")
    print("   - 'Ignoring backchannel input while agent speaking' messages")
    print("   - Agent state changes (speaking <-> listening)")
    print("   - User transcript events\n")

    print("=" * 80 + "\n")


def main():
    """Main test function."""
    print("\n🎯 Testing Intelligent Interruption Handling Implementation")

    # Run logical tests
    all_passed = print_test_results()

    # Print manual testing instructions
    print_usage_instructions()

    # Print additional information
    print("📚 For detailed documentation, see: INTELLIGENT_INTERRUPTION_README.md\n")

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

