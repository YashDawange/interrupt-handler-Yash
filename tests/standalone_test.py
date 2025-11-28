#!/usr/bin/env python3
"""
Standalone test for interruption filter logic (no dependencies)
"""

import re
from typing import Literal
from dataclasses import dataclass


@dataclass
class InterruptionDecision:
    should_interrupt: bool
    reason: str
    matched_words: list


class InterruptionFilter:
    DEFAULT_IGNORE_LIST = ["yeah", "ok", "okay", "hmm", "uh-huh", "mm-hmm", "right", "aha", "mhm", "uh", "um", "huh", "mm"]
    DEFAULT_COMMAND_LIST = ["wait", "stop", "no", "hold", "pause", "but", "actually"]

    def __init__(self, ignore_list=None, command_list=None):
        ignore_list = ignore_list or self.DEFAULT_IGNORE_LIST
        command_list = command_list or self.DEFAULT_COMMAND_LIST
        self._ignore_set = set(w.lower() for w in ignore_list)
        self._command_set = set(w.lower() for w in command_list)

    def should_interrupt(self, transcript: str, agent_state: Literal["speaking", "listening", "thinking"]) -> InterruptionDecision:
        normalized = transcript.lower().strip()
        
        if not normalized:
            return InterruptionDecision(False, "Empty transcript", [])
        
        if agent_state != "speaking":
            return InterruptionDecision(True, f"Agent is {agent_state}, processing user input normally", [])
        
        words = self._tokenize(normalized)
        
        command_matches = [w for w in words if w in self._command_set]
        if command_matches:
            return InterruptionDecision(True, "Command word detected while agent speaking", command_matches)
        
        ignore_matches = [w for w in words if w in self._ignore_set]
        non_ignore_words = [w for w in words if w not in self._ignore_set]
        
        if non_ignore_words:
            return InterruptionDecision(True, "Non-filler content detected while agent speaking", non_ignore_words)
        
        return InterruptionDecision(False, "Only filler words detected while agent speaking", ignore_matches)

    def _tokenize(self, text: str) -> list:
        text = re.sub(r"[^\w\s-]", " ", text)
        words = text.split()
        result = []
        for word in words:
            if "-" in word:
                result.append(word)
                result.extend(word.split("-"))
            else:
                result.append(word)
        return [w.strip() for w in result if w.strip()]


def run_test(name, test_func):
    """Run a single test and report results"""
    try:
        test_func()
        print(f"  ✅ {name}")
        return True
    except AssertionError as e:
        print(f"  ❌ {name}: {e}")
        return False


def test_scenario_1():
    """Scenario 1: Filler words while speaking -> NO interruption"""
    filter = InterruptionFilter()
    for word in ["yeah", "ok", "hmm", "uh-huh"]:
        decision = filter.should_interrupt(word, "speaking")
        assert not decision.should_interrupt, f"'{word}' should not interrupt"


def test_scenario_2():
    """Scenario 2: Command words while speaking -> YES interruption"""
    filter = InterruptionFilter()
    for word in ["wait", "stop", "no", "pause"]:
        decision = filter.should_interrupt(word, "speaking")
        assert decision.should_interrupt, f"'{word}' should interrupt"


def test_scenario_3():
    """Scenario 3: Mixed input -> YES interruption"""
    filter = InterruptionFilter()
    for phrase in ["yeah wait", "ok but stop", "hmm actually"]:
        decision = filter.should_interrupt(phrase, "speaking")
        assert decision.should_interrupt, f"'{phrase}' should interrupt"


def test_scenario_4():
    """Scenario 4: Any input while silent -> YES processing"""
    filter = InterruptionFilter()
    for word in ["yeah", "ok", "hello", "wait"]:
        decision = filter.should_interrupt(word, "listening")
        assert decision.should_interrupt, f"'{word}' should be processed when silent"


def test_empty():
    """Empty transcript should not interrupt"""
    filter = InterruptionFilter()
    decision = filter.should_interrupt("", "speaking")
    assert not decision.should_interrupt


def test_case_insensitive():
    """Case insensitivity"""
    filter = InterruptionFilter()
    decision = filter.should_interrupt("YEAH", "speaking")
    assert not decision.should_interrupt
    decision = filter.should_interrupt("STOP", "speaking")
    assert decision.should_interrupt


def test_punctuation():
    """Punctuation handling"""
    filter = InterruptionFilter()
    decision = filter.should_interrupt("yeah!", "speaking")
    assert not decision.should_interrupt
    decision = filter.should_interrupt("stop.", "speaking")
    assert decision.should_interrupt


def main():
    print("=" * 70)
    print("Intelligent Interruption Filter - Test Suite")
    print("=" * 70)
    
    tests = [
        ("Scenario 1: Filler while speaking", test_scenario_1),
        ("Scenario 2: Command while speaking", test_scenario_2),
        ("Scenario 3: Mixed input", test_scenario_3),
        ("Scenario 4: Input while silent", test_scenario_4),
        ("Edge case: Empty transcript", test_empty),
        ("Edge case: Case insensitivity", test_case_insensitive),
        ("Edge case: Punctuation", test_punctuation),
    ]
    
    passed = sum(1 for name, func in tests if run_test(name, func))
    total = len(tests)
    
    print("=" * 70)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
