"""
Simple test for the Intelligent Interruption Handler logic

This tests the core logic without importing modules.
"""

import re
from dataclasses import dataclass
from typing import Sequence


@dataclass
class InterruptionConfig:
    """Configuration for intelligent interruption handling."""
    ignore_words: Sequence[str] = (
        "yeah", "ok", "okay", "hmm", "uh-huh", "mhm", "right", 
        "aha", "gotcha", "sure", "yep", "yup", "mm-hmm"
    )
    case_sensitive: bool = False
    enabled: bool = True


class InterruptionHandler:
    """Handles context-aware interruption filtering."""
    
    def __init__(self, config: InterruptionConfig | None = None) -> None:
        self.config = config or InterruptionConfig()
        self._ignore_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> list:
        """Compile regex patterns for ignore words."""
        patterns = []
        for word in self.config.ignore_words:
            flags = 0 if self.config.case_sensitive else re.IGNORECASE
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', flags)
            patterns.append(pattern)
        return patterns
    
    def should_ignore_transcript(self, transcript: str, agent_state: str) -> bool:
        """Determine if a transcript should be ignored based on agent state."""
        if not self.config.enabled:
            return False
        
        if agent_state != "speaking":
            return False
        
        text = transcript.strip()
        if not text:
            return False
        
        words = re.findall(r'\b\w+\b', text)
        if not words:
            return False
        
        matched_words = set()
        for word in words:
            for pattern in self._ignore_patterns:
                if pattern.fullmatch(word):
                    matched_words.add(word.lower())
                    break
        
        all_words_match = len(matched_words) == len(set(w.lower() for w in words))
        return all_words_match
    
    def should_interrupt(self, transcript: str, agent_state: str) -> bool:
        """Determine if a transcript should trigger an interruption."""
        return not self.should_ignore_transcript(transcript, agent_state)


def run_tests():
    """Run all test scenarios"""
    print("\n" + "="*80)
    print("INTELLIGENT INTERRUPTION HANDLER TESTS")
    print("="*80)
    
    handler = InterruptionHandler()
    
    # Scenario 1: Agent speaking, user says backchanneling
    print("\n📋 SCENARIO 1: Long Explanation (Agent speaking)")
    print("-"*80)
    test_cases = [
        ("yeah", "speaking", True, "Backchanneling - should ignore"),
        ("ok", "speaking", True, "Backchanneling - should ignore"),
        ("hmm", "speaking", True, "Backchanneling - should ignore"),
        ("okay yeah", "speaking", True, "Multiple backchannels - should ignore"),
    ]
    
    for transcript, state, expected_ignore, desc in test_cases:
        result = handler.should_ignore_transcript(transcript, state)
        status = "✅ PASS" if result == expected_ignore else "❌ FAIL"
        print(f"{status} | '{transcript}' | {desc}")
    
    # Scenario 2: Agent silent, user says backchanneling
    print("\n📋 SCENARIO 2: Passive Affirmation (Agent silent)")
    print("-"*80)
    test_cases = [
        ("yeah", "listening", False, "Should respond when agent silent"),
        ("ok", "listening", False, "Should respond when agent silent"),
        ("hmm", "thinking", False, "Should respond when agent thinking"),
    ]
    
    for transcript, state, expected_ignore, desc in test_cases:
        result = handler.should_ignore_transcript(transcript, state)
        status = "✅ PASS" if result == expected_ignore else "❌ FAIL"
        print(f"{status} | '{transcript}' | {desc}")
    
    # Scenario 3: Agent speaking, user gives command
    print("\n📋 SCENARIO 3: Active Interruption (Agent speaking, user commands)")
    print("-"*80)
    test_cases = [
        ("stop", "speaking", False, "Command - should interrupt"),
        ("wait", "speaking", False, "Command - should interrupt"),
        ("no", "speaking", False, "Command - should interrupt"),
        ("no stop", "speaking", False, "Command - should interrupt"),
    ]
    
    for transcript, state, expected_ignore, desc in test_cases:
        result = handler.should_ignore_transcript(transcript, state)
        status = "✅ PASS" if result == expected_ignore else "❌ FAIL"
        print(f"{status} | '{transcript}' | {desc}")
    
    # Scenario 4: Mixed input
    print("\n📋 SCENARIO 4: Mixed Input")
    print("-"*80)
    test_cases = [
        ("yeah wait", "speaking", False, "Contains command - should interrupt"),
        ("yeah okay but wait", "speaking", False, "Contains command - should interrupt"),
        ("ok stop", "speaking", False, "Contains command - should interrupt"),
        ("hmm actually", "speaking", False, "Contains non-ignore word - should interrupt"),
    ]
    
    for transcript, state, expected_ignore, desc in test_cases:
        result = handler.should_ignore_transcript(transcript, state)
        status = "✅ PASS" if result == expected_ignore else "❌ FAIL"
        print(f"{status} | '{transcript}' | {desc}")
    
    # Edge cases
    print("\n📋 EDGE CASES")
    print("-"*80)
    test_cases = [
        ("", "speaking", False, "Empty string"),
        ("YEAH", "speaking", True, "Case insensitive"),
        ("year", "speaking", False, "Similar but not in list"),
        ("yeah yeah yeah", "speaking", True, "Repeated ignore word"),
    ]
    
    for transcript, state, expected_ignore, desc in test_cases:
        result = handler.should_ignore_transcript(transcript, state)
        status = "✅ PASS" if result == expected_ignore else "❌ FAIL"
        print(f"{status} | '{transcript}' | {desc}")
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    run_tests()
