"""Standalone test for interruption filter logic."""

import re
from typing import Set

# Copy of the filter logic for standalone testing
class InterruptionFilter:
    def __init__(
        self,
        *,
        backchannel_words: Set[str] | None = None,
        command_words: Set[str] | None = None,
        enabled: bool = True,
    ):
        default_backchannel = {
            "yeah", "yes", "yep", "yup", "ok", "okay", "kay", "hmm", "hm", "mhm", "mm",
            "uh-huh", "uh huh", "uhuh", "right", "aha", "ah", "uh", "um", "sure", "got it", "i see",
        }
        default_command = {
            "stop", "wait", "hold on", "hold up", "pause", "no", "nope", "but",
            "however", "actually", "excuse me", "sorry", "pardon",
        }
        
        self.backchannel_words = (
            backchannel_words if backchannel_words is not None else default_backchannel.copy()
        )
        self.command_words = (
            command_words if command_words is not None else default_command.copy()
        )
        self.enabled = enabled
        
        self.backchannel_words = {w.lower() for w in self.backchannel_words}
        self.command_words = {w.lower() for w in self.command_words}
    
    def should_interrupt(self, transcript: str, agent_is_speaking: bool) -> bool:
        if not self.enabled:
            return True
        
        if not agent_is_speaking:
            return True
        
        if not transcript or not transcript.strip():
            return False
        
        normalized_transcript = transcript.lower().strip()
        
        if self._contains_command_words(normalized_transcript):
            return True
        
        if self._is_only_backchannel(normalized_transcript):
            return False
        
        return True
    
    def _contains_command_words(self, normalized_transcript: str) -> bool:
        words = self._extract_words(normalized_transcript)
        
        if any(word in self.command_words for word in words):
            return True
        
        for command in self.command_words:
            if ' ' in command and command in normalized_transcript:
                return True
        
        return False
    
    def _is_only_backchannel(self, normalized_transcript: str) -> bool:
        words = self._extract_words(normalized_transcript)
        
        if not words:
            return False
        
        for word in words:
            if word in self.backchannel_words:
                continue
            
            is_part_of_backchannel = False
            for backchannel in self.backchannel_words:
                if ' ' in backchannel or '-' in backchannel:
                    backchannel_words = re.split(r'[\s\-]+', backchannel)
                    if word in backchannel_words:
                        is_part_of_backchannel = True
                        break
            
            if not is_part_of_backchannel:
                return False
        
        for backchannel in self.backchannel_words:
            if (' ' in backchannel or '-' in backchannel) and backchannel in normalized_transcript:
                if normalized_transcript.replace('-', ' ') == backchannel.replace('-', ' '):
                    return True
        
        return True
    
    def _extract_words(self, text: str) -> list[str]:
        words = re.findall(r'\b\w+\b', text.lower())
        return words


def run_test(name: str, tests: list[tuple[str, bool, bool]]) -> bool:
    """Run a set of tests."""
    print(f"\n{name}:")
    filter = InterruptionFilter()
    all_passed = True
    
    for transcript, agent_speaking, expected in tests:
        result = filter.should_interrupt(transcript, agent_is_speaking=agent_speaking)
        passed = result == expected
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} '{transcript}' (agent_speaking={agent_speaking}): {result} (expected {expected})")
        if not passed:
            all_passed = False
    
    return all_passed


def main():
    print("=" * 70)
    print("Testing Intelligent Interruption Filter")
    print("=" * 70)
    
    all_tests_passed = True
    
    # Test 1: Backchannel ignored when agent is speaking
    all_tests_passed &= run_test(
        "Test 1: Backchannel ignored when agent is speaking",
        [
            ("yeah", True, False),
            ("ok", True, False),
            ("hmm", True, False),
            ("uh-huh", True, False),
            ("right", True, False),
            ("yeah ok", True, False),
            ("ok yeah hmm", True, False),
        ]
    )
    
    # Test 2: Command words interrupt when agent is speaking
    all_tests_passed &= run_test(
        "Test 2: Command words interrupt when agent is speaking",
        [
            ("stop", True, True),
            ("wait", True, True),
            ("no", True, True),
            ("hold on", True, True),
            ("pause", True, True),
        ]
    )
    
    # Test 3: Mixed input interrupts
    all_tests_passed &= run_test(
        "Test 3: Mixed input (backchannel + command) interrupts",
        [
            ("yeah wait", True, True),
            ("ok but", True, True),
            ("yeah wait a second", True, True),
            ("hmm actually", True, True),
        ]
    )
    
    # Test 4: Agent not speaking - all input processed
    all_tests_passed &= run_test(
        "Test 4: Agent not speaking - all input processed",
        [
            ("yeah", False, True),
            ("stop", False, True),
            ("hello there", False, True),
        ]
    )
    
    # Test 5: Other input interrupts
    all_tests_passed &= run_test(
        "Test 5: Other input (not backchannel) interrupts",
        [
            ("tell me more", True, True),
            ("what about", True, True),
            ("can you explain", True, True),
            ("I have a question", True, True),
        ]
    )
    
    # Test 6: Case insensitive
    all_tests_passed &= run_test(
        "Test 6: Case insensitive matching",
        [
            ("YEAH", True, False),
            ("Ok", True, False),
            ("HMM", True, False),
            ("STOP", True, True),
            ("Wait", True, True),
        ]
    )
    
    # Test 7: Punctuation handling
    all_tests_passed &= run_test(
        "Test 7: Punctuation handling",
        [
            ("yeah.", True, False),
            ("ok!", True, False),
            ("hmm...", True, False),
            ("stop!", True, True),
        ]
    )
    
    # Test 8: Empty transcript
    all_tests_passed &= run_test(
        "Test 8: Empty transcript doesn't interrupt",
        [
            ("", True, False),
            ("   ", True, False),
        ]
    )
    
    # Test 9: Scenario tests from requirements
    all_tests_passed &= run_test(
        "Test 9: Scenario 1 - Long explanation with backchannels",
        [
            ("Okay", True, False),
            ("yeah", True, False),
            ("uh-huh", True, False),
            ("okay yeah uh-huh", True, False),
        ]
    )
    
    all_tests_passed &= run_test(
        "Test 10: Scenario 2 - Passive affirmation when silent",
        [
            ("Yeah", False, True),
        ]
    )
    
    all_tests_passed &= run_test(
        "Test 11: Scenario 3 - Correction",
        [
            ("No stop", True, True),
            ("No", True, True),
            ("stop", True, True),
        ]
    )
    
    all_tests_passed &= run_test(
        "Test 12: Scenario 4 - Mixed input",
        [
            ("Yeah okay but wait", True, True),
            ("yeah but", True, True),
            ("ok wait", True, True),
        ]
    )
    
    print("\n" + "=" * 70)
    if all_tests_passed:
        print("[SUCCESS] ALL TESTS PASSED")
    else:
        print("[FAILURE] SOME TESTS FAILED")
    print("=" * 70)
    
    return all_tests_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
