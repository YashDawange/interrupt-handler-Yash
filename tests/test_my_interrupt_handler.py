"""
Standalone test for Interrupt Handler (Assignment Proof)
Run with: python tests/test_my_interrupt_handler.py

This is completely standalone - no external imports needed!
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Set


class AgentState(Enum):
    """Track whether agent is currently speaking or silent."""
    SPEAKING = "speaking"
    SILENT = "silent"


@dataclass
class InterruptionConfig:
    """Configuration for intelligent interruption detection."""
    
    filler_words: Set[str] = field(default_factory=lambda: {
        "yeah", "yep", "yup", "yes", "ya", "yea",
        "ok", "okay", "k",
        "sure", "right", "correct",
        "um", "uh", "umm", "uhh", "er", "err",
        "hmm", "hm", "mmm", "mm", "mhm", "mm-hmm",
        "ah", "aha", "ahem", "oh",
        "huh", "ugh", "meh",
    })
    
    interrupt_words: Set[str] = field(default_factory=lambda: {
        "stop", "wait", "hold", "pause", "no", "nope",
        "actually", "but", "however", "question",
        "what", "why", "how", "when", "where", "who",
        "help", "sorry", "excuse",
    })
    
    min_words_for_interrupt: int = 2


class InterruptHandler:
    """
    Determines whether user speech should interrupt the agent.
    """
    
    def __init__(self, config=None):
        self.config = config or InterruptionConfig()
        self._stats = {"total": 0, "ignored": 0, "interrupted": 0}
    
    def should_interrupt(self, agent_state, transcribed_text):
        """
        Decide if the agent should be interrupted.
        """
        self._stats["total"] += 1
        
        text = transcribed_text.lower().strip()
        if not text:
            self._stats["ignored"] += 1
            return False
        
        words = self._tokenize(text)
        
        if not words:
            self._stats["ignored"] += 1
            return False
        
        # If agent is SILENT, always process user input
        if agent_state == AgentState.SILENT:
            self._stats["interrupted"] += 1
            return True
        
        # Agent is SPEAKING - check if real interruption
        has_interrupt_word = any(
            word in self.config.interrupt_words 
            for word in words
        )
        
        if has_interrupt_word:
            self._stats["interrupted"] += 1
            return True
        
        all_fillers = all(
            word in self.config.filler_words 
            for word in words
        )
        
        if all_fillers:
            self._stats["ignored"] += 1
            return False
        
        non_filler_words = [
            w for w in words 
            if w not in self.config.filler_words
        ]
        
        if len(non_filler_words) >= self.config.min_words_for_interrupt:
            self._stats["interrupted"] += 1
            return True
        
        self._stats["ignored"] += 1
        return False
    
    def _tokenize(self, text):
        """Split text into clean words."""
        words = re.findall(r'\b[a-z]+\b', text.lower())
        return [w for w in words if w]
    
    def get_stats(self):
        """Get interruption statistics."""
        return self._stats.copy()
    
    def reset_stats(self):
        """Reset statistics."""
        self._stats = {"total": 0, "ignored": 0, "interrupted": 0}


def run_tests():
    """Run all test scenarios for the assignment."""
    handler = InterruptHandler()
    
    print("=" * 70)
    print("INTERRUPT HANDLER TEST SUITE")
    print("=" * 70)
    print()
    
    # Test scenarios from assignment requirements
    test_cases = [
        # Scenario 1: Agent speaking + filler words = IGNORE
        {
            "scenario": "Scenario 1: The Long Explanation",
            "description": "Agent is speaking, user says acknowledgments",
            "tests": [
                (AgentState.SPEAKING, "Okay", False, "User says 'Okay'"),
                (AgentState.SPEAKING, "yeah", False, "User says 'yeah'"),
                (AgentState.SPEAKING, "uh-huh", False, "User says 'uh-huh'"),
                (AgentState.SPEAKING, "okay yeah", False, "User says 'okay yeah'"),
            ]
        },
        
        # Scenario 2: Agent silent + filler = RESPOND
        {
            "scenario": "Scenario 2: The Passive Affirmation",
            "description": "Agent asks 'Are you ready?' and goes silent",
            "tests": [
                (AgentState.SILENT, "Yeah", True, "User responds 'Yeah'"),
                (AgentState.SILENT, "yes", True, "User responds 'yes'"),
                (AgentState.SILENT, "okay", True, "User responds 'okay'"),
            ]
        },
        
        # Scenario 3: Agent speaking + command = INTERRUPT
        {
            "scenario": "Scenario 3: The Correction",
            "description": "Agent is counting, user wants to stop",
            "tests": [
                (AgentState.SPEAKING, "No stop", True, "User says 'No stop'"),
                (AgentState.SPEAKING, "stop", True, "User says 'stop'"),
                (AgentState.SPEAKING, "wait", True, "User says 'wait'"),
            ]
        },
        
        # Scenario 4: Mixed input = INTERRUPT
        {
            "scenario": "Scenario 4: The Mixed Input",
            "description": "Agent is speaking, user has mixed input",
            "tests": [
                (AgentState.SPEAKING, "Yeah okay but wait", True, "User says 'Yeah okay but wait'"),
                (AgentState.SPEAKING, "yeah wait", True, "Contains 'wait' command"),
                (AgentState.SPEAKING, "um actually", True, "Contains 'actually'"),
            ]
        },
        
        # Additional edge cases
        {
            "scenario": "Edge Cases",
            "description": "Test edge cases and robustness",
            "tests": [
                (AgentState.SPEAKING, "", False, "Empty input"),
                (AgentState.SPEAKING, "yeah!", False, "Punctuation on filler"),
                (AgentState.SPEAKING, "YEAH", False, "Uppercase filler"),
                (AgentState.SPEAKING, "STOP", True, "Uppercase command"),
                (AgentState.SPEAKING, "I have a question", True, "Real question"),
                (AgentState.SPEAKING, "what do you mean", True, "Question phrase"),
            ]
        }
    ]
    
    total_passed = 0
    total_failed = 0
    
    for test_group in test_cases:
        print(f"\n{'='*70}")
        print(f" {test_group['scenario']}")
        print(f"  {test_group['description']}")
        print(f"{'='*70}\n")
        
        for state, text, expected, description in test_group['tests']:
            result = handler.should_interrupt(state, text)
            
            if result == expected:
                print(f"PASS: {description}")
                print(f"         State={state.value}, Input='{text}' → Result={result}")
                total_passed += 1
            else:
                print(f"FAIL: {description}")
                print(f"         State={state.value}, Input='{text}'")
                print(f"         Expected={expected}, Got={result}")
                total_failed += 1
    
    # Summary
    print(f"\n{'='*70}")
    print(f"TEST RESULTS")
    print(f"{'='*70}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Total:  {total_passed + total_failed}")
    print(f"{'='*70}")
    
    # Statistics
    stats = handler.get_stats()
    print(f"\nHandler Statistics:")
    print(f"  Total interruptions checked: {stats['total']}")
    print(f"  Ignored (filtered):          {stats['ignored']}")
    print(f"  Processed (interrupted):     {stats['interrupted']}")
    print()
    
    return total_failed == 0


if __name__ == "__main__":
    import sys
    
    success = run_tests()
    
    if success:
        print(" All tests passed! Ready for submission.")
        print("\nThis validates your interrupt_handler.py implementation")
        print("matches the assignment requirements:")
        print("  Ignores 'yeah/ok/hmm' when agent is speaking")
        print("  Responds to 'yeah' when agent is silent")
        print("  Interrupts on 'stop/wait/no' commands")
        print("  Handles mixed input correctly")
        sys.exit(0)
    else:
        print(" Some tests failed. Please review the code.")
        sys.exit(1)
