"""
Simple unit test to verify backchannel detection logic

This script tests the word matching logic independently of the full LiveKit stack.
No LiveKit installation required - uses simple word splitting.
"""

import re

# Default backchannel words from our implementation
DEFAULT_BACKCHANNEL_WORDS = [
    "yeah", "ok", "okay", "hmm", "mm-hmm", "uh-huh",
    "right", "aha", "ah", "mhm", "yep", "yup",
    "sure", "gotcha", "alright"
]


def simple_split_words(text: str) -> list[str]:
    """Simple word splitting for testing (mimics split_words behavior)"""
    # Split on whitespace and common punctuation
    words = re.findall(r'\b[\w-]+\b', text)
    return words


def is_backchannel_only(transcript: str, backchannel_words: list[str]) -> bool:
    """
    Check if a transcript contains ONLY backchannel words.

    Returns True if all words are backchannel words, False otherwise.
    """
    transcript = transcript.strip()

    if not transcript:
        return False

    # Split into words
    words = simple_split_words(transcript)

    # Normalize: lowercase and strip punctuation
    normalized_words = [
        word.lower().strip(".,!?;:'\"")
        for word in words
    ]

    # Remove empty strings
    normalized_words = [w for w in normalized_words if w]

    if not normalized_words:
        return False

    # Check if ALL words are backchannel
    backchannel_set = set(word.lower() for word in backchannel_words)
    is_all_backchannel = all(
        word in backchannel_set
        for word in normalized_words
    )

    return is_all_backchannel


def test_backchannel_detection():
    """Run test cases for backchannel detection"""

    test_cases = [
        # (transcript, expected_is_backchannel, description)
        ("yeah", True, "Single backchannel word"),
        ("ok", True, "Another single backchannel word"),
        ("yeah ok", True, "Multiple backchannel words"),
        ("yeah, ok, hmm", True, "Backchannel with punctuation"),
        ("Yeah!", True, "Backchannel with exclamation"),
        ("stop", False, "Command word (not backchannel)"),
        ("wait", False, "Another command word"),
        ("yeah wait", False, "Mixed: backchannel + command"),
        ("yeah but wait", False, "Mixed: backchannel + filler + command"),
        ("ok stop", False, "Mixed: backchannel + command"),
        ("tell me more", False, "Regular user input"),
        ("", False, "Empty string"),
        ("   ", False, "Whitespace only"),
        ("Yeah... okay... mm-hmm", True, "Multiple backchannel with punctuation"),
        ("right right right", True, "Repeated backchannel"),
        ("no", False, "Negation (command)"),
        ("yes", False, "Affirmation (not in default list)"),
        ("uh-huh yeah", True, "Hyphenated backchannel"),
        ("gotcha!", True, "Casual backchannel with punctuation"),
        ("yeah, I understand", False, "Backchannel + sentence"),
    ]

    print("Testing Backchannel Detection Logic")
    print("=" * 60)

    passed = 0
    failed = 0

    for transcript, expected, description in test_cases:
        result = is_backchannel_only(transcript, DEFAULT_BACKCHANNEL_WORDS)
        status = "✅ PASS" if result == expected else "❌ FAIL"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} | '{transcript}' | Expected: {expected}, Got: {result}")
        print(f"       Description: {description}")
        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")

    if failed == 0:
        print("✅ All tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


def test_agent_scenarios():
    """Test the 4 main scenarios from the assignment"""

    print("\n")
    print("Testing Assignment Scenarios")
    print("=" * 60)

    scenarios = [
        {
            "name": "Scenario 1: The Long Explanation",
            "agent_state": "speaking",
            "user_input": "Okay... yeah... uh-huh",
            "expected_behavior": "IGNORE (continue speaking)",
        },
        {
            "name": "Scenario 2: The Passive Affirmation",
            "agent_state": "silent",
            "user_input": "Yeah.",
            "expected_behavior": "RESPOND (treat as valid input)",
        },
        {
            "name": "Scenario 3: The Correction",
            "agent_state": "speaking",
            "user_input": "No stop.",
            "expected_behavior": "INTERRUPT (stop immediately)",
        },
        {
            "name": "Scenario 4: The Mixed Input",
            "agent_state": "speaking",
            "user_input": "Yeah okay but wait.",
            "expected_behavior": "INTERRUPT (contains command)",
        },
    ]

    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print(f"  Agent State: {scenario['agent_state']}")
        print(f"  User Input: '{scenario['user_input']}'")

        is_backchannel = is_backchannel_only(scenario["user_input"], DEFAULT_BACKCHANNEL_WORDS)

        if scenario["agent_state"] == "speaking":
            if is_backchannel:
                behavior = "IGNORE (continue speaking)"
            else:
                behavior = "INTERRUPT (stop immediately)"
        else:  # silent
            behavior = "RESPOND (treat as valid input)"

        expected = scenario["expected_behavior"]
        status = "✅" if behavior == expected else "❌"

        print(f"  Expected: {expected}")
        print(f"  {status} Actual: {behavior}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run unit tests
    all_passed = test_backchannel_detection()

    # Run scenario tests
    test_agent_scenarios()

    if all_passed:
        print("\n✅ Implementation is ready for submission!")
    else:
        print("\n❌ Please review failed tests")
