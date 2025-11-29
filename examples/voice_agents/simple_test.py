#!/usr/bin/env python3
"""
Simple test for the IntelligentInterruptionHandler without requiring all dependencies.
"""

import re
from typing import Set


class SimpleInterruptionHandler:
    """
    Simplified version of the IntelligentInterruptionHandler for testing.
    """
    
    def __init__(self):
        self.ignore_list: Set[str] = {
            'yeah', 'ok', 'hmm', 'right', 'uh-huh', 'yep', 'yup', 'aha', 'mmm', 'got it',
            'i see', 'i know', 'sure', 'okay', 'yes', 'yuppers', 'uhuh', 'mhm'
        }
        self.interrupt_list: Set[str] = {
            'wait', 'stop', 'no', 'cancel', 'hold on', 'please stop', 'never mind',
            'shut up', 'quiet', 'silence'
        }
        
    def should_ignore_input(self, text: str, agent_speaking: bool) -> bool:
        """
        Determines if user input should be ignored based on agent state and input content.
        
        Args:
            text: The user's transcribed input
            agent_speaking: Whether the agent is currently speaking
            
        Returns:
            True if the input should be ignored, False otherwise
        """
        normalized_text = self._normalize_text(text)
        
        if not agent_speaking:
            return False
            
        words = normalized_text.split()
        
        if len(words) == 1 and words[0] in self.ignore_list:
            return True
            
        for word in words:
            if word in self.interrupt_list:
                return False
                
        all_passive = all(word in self.ignore_list for word in words)
        return all_passive and agent_speaking
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison by lowercasing and removing punctuation."""
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = ' '.join(normalized.split())
        return normalized


def test_interruption_handler():
    """Test the interruption handler logic."""
    handler = SimpleInterruptionHandler()
    
    test_cases = [
        ("yeah", True, True, "Single passive word while speaking should be ignored"),
        ("ok", True, True, "Single passive word while speaking should be ignored"),
        ("hmm", True, True, "Single passive word while speaking should be ignored"),
        ("yeah", False, False, "Single passive word while silent should NOT be ignored"),
        ("stop", True, False, "Interrupt word while speaking should NOT be ignored"),
        ("wait", True, False, "Interrupt word while speaking should NOT be ignored"),
        ("yeah ok hmm", True, True, "Multiple passive words while speaking should be ignored"),
        ("yeah wait", True, False, "Mixed words with interrupt while speaking should NOT be ignored"),
        ("YEAH", True, True, "Case insensitive passive word should be ignored"),
        ("yeah!", True, True, "Punctuation should be removed for passive word"),
        ("  yeah  ", True, True, "Extra whitespace should be handled"),
    ]
    
    print("Running interruption handler tests...")
    passed = 0
    failed = 0
    
    for text, agent_speaking, expected, description in test_cases:
        result = handler.should_ignore_input(text, agent_speaking)
        if result == expected:
            print(f"✓ PASS: {description}")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Input: '{text}', Agent speaking: {agent_speaking}")
            print(f"  Expected: {expected}, Got: {result}")
            failed += 1
    
    print(f"\nTest Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = test_interruption_handler()
    exit(0 if success else 1)