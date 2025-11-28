#!/usr/bin/env python3
"""
Interactive Demo of Intelligent Interruption Filter (Standalone)

This script demonstrates the intelligent interruption handling
without requiring any dependencies.
"""

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class InterruptionDecision:
    """Result of interruption filtering decision"""
    should_interrupt: bool
    reason: str
    matched_words: list


class InterruptionFilter:
    """Context-aware filter for intelligent interruption handling"""
    
    DEFAULT_IGNORE_LIST = [
        "yeah", "ok", "okay", "hmm", "uh-huh", "mm-hmm", 
        "right", "aha", "mhm", "uh", "um", "huh", "mm"
    ]
    
    DEFAULT_COMMAND_LIST = [
        "wait", "stop", "no", "hold", "pause", 
        "but", "actually", "however"
    ]
    
    def __init__(self):
        self._ignore_set = set(w.lower() for w in self.DEFAULT_IGNORE_LIST)
        self._command_set = set(w.lower() for w in self.DEFAULT_COMMAND_LIST)
    
    def should_interrupt(
        self, 
        transcript: str, 
        agent_state: Literal["speaking", "listening", "thinking"]
    ) -> InterruptionDecision:
        """Determine if user speech should interrupt the agent"""
        normalized = transcript.lower().strip()
        
        if not normalized:
            return InterruptionDecision(False, "Empty transcript", [])
        
        # When agent is not speaking, always process input
        if agent_state != "speaking":
            return InterruptionDecision(
                True, 
                f"Agent is {agent_state}, processing user input normally", 
                []
            )
        
        # Agent is speaking - apply intelligent filtering
        words = self._tokenize(normalized)
        
        # Check for command words first
        command_matches = [w for w in words if w in self._command_set]
        if command_matches:
            return InterruptionDecision(
                True, 
                "Command word detected while agent speaking", 
                command_matches
            )
        
        # Check if all words are in ignore list
        non_ignore_words = [w for w in words if w not in self._ignore_set]
        
        if non_ignore_words:
            return InterruptionDecision(
                True, 
                "Non-filler content detected while agent speaking", 
                non_ignore_words
            )
        
        # All words are filler/backchanneling
        ignore_matches = [w for w in words if w in self._ignore_set]
        return InterruptionDecision(
            False, 
            "Only filler words detected while agent speaking", 
            ignore_matches
        )
    
    def _tokenize(self, text: str) -> list:
        """Tokenize text into words"""
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


def print_banner(text):
    """Print a banner for section headers"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def demo_scenario(scenario_num, title, agent_state, user_inputs, expected_results):
    """Run a demo scenario and show results"""
    print(f"\n🎯 Scenario {scenario_num}: {title}")
    print(f"   Agent State: {agent_state.upper()}")
    print("-" * 70)
    
    filter = InterruptionFilter()
    all_passed = True
    
    for i, (user_input, expected) in enumerate(zip(user_inputs, expected_results), 1):
        decision = filter.should_interrupt(user_input, agent_state)
        
        matches = decision.should_interrupt == expected
        all_passed = all_passed and matches
        status = "✅" if matches else "❌"
        
        print(f"\n   Test {i}:")
        print(f"   User says: \"{user_input}\"")
        print(f"   Expected:  {'INTERRUPT' if expected else 'CONTINUE (ignore)'}")
        print(f"   Decision:  {'INTERRUPT' if decision.should_interrupt else 'CONTINUE (ignore)'}")
        print(f"   Reason:    {decision.reason}")
        if decision.matched_words:
            print(f"   Matched:   {decision.matched_words}")
        print(f"   Result:    {status} {'PASS' if matches else 'FAIL'}")
    
    print(f"\n   {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    return all_passed


def main():
    print_banner("Intelligent Interruption Filter - Interactive Demo")
    print("\nThis demo simulates the four key scenarios from the assignment:")
    print("1. Agent speaking + filler words → NO interruption")
    print("2. Agent speaking + command words → YES interruption")
    print("3. Agent speaking + mixed input → YES interruption")
    print("4. Agent silent + any input → YES processing")
    
    all_scenarios_passed = True
    
    # Scenario 1: The Long Explanation
    passed = demo_scenario(
        scenario_num=1,
        title="The Long Explanation (Agent is explaining history)",
        agent_state="speaking",
        user_inputs=[
            "yeah",
            "okay",
            "hmm",
            "uh-huh",
            "yeah yeah okay",
            "okay... yeah... uh-huh",
        ],
        expected_results=[False, False, False, False, False, False]
    )
    all_scenarios_passed = all_scenarios_passed and passed
    
    # Scenario 2: The Correction
    passed = demo_scenario(
        scenario_num=2,
        title="The Correction (Agent is counting)",
        agent_state="speaking",
        user_inputs=[
            "no",
            "stop",
            "wait",
            "hold on",
            "no stop",
            "Stop please",
        ],
        expected_results=[True, True, True, True, True, True]
    )
    all_scenarios_passed = all_scenarios_passed and passed
    
    # Scenario 3: The Mixed Input
    passed = demo_scenario(
        scenario_num=3,
        title="The Mixed Input (Agent is explaining)",
        agent_state="speaking",
        user_inputs=[
            "yeah wait",
            "okay but wait",
            "hmm actually no",
            "yeah okay but stop",
            "uh-huh however that's wrong",
        ],
        expected_results=[True, True, True, True, True]
    )
    all_scenarios_passed = all_scenarios_passed and passed
    
    # Scenario 4: The Passive Affirmation
    passed = demo_scenario(
        scenario_num=4,
        title="The Passive Affirmation (Agent is silent, waiting)",
        agent_state="listening",
        user_inputs=[
            "yeah",
            "okay",
            "yes",
            "sure",
            "tell me more",
            "hello",
        ],
        expected_results=[True, True, True, True, True, True]
    )
    all_scenarios_passed = all_scenarios_passed and passed
    
    # Summary
    print_banner("Demo Summary")
    if all_scenarios_passed:
        print("\n✅ ALL SCENARIOS PASSED!")
    else:
        print("\n❌ SOME SCENARIOS FAILED")
    
    print("\n📊 Configuration:")
    filter = InterruptionFilter()
    print(f"   Ignore List:  {sorted(filter._ignore_set)}")
    print(f"   Command List: {sorted(filter._command_set)}")
    
    print("\n🎓 Key Takeaways:")
    print("  • Filler words (yeah, ok, hmm) are ignored when agent is speaking")
    print("  • Command words (wait, stop, no) always trigger interruption")
    print("  • Mixed input with commands triggers interruption")
    print("  • All input is processed normally when agent is silent")
    
    print_banner("Demo Complete")
    
    return 0 if all_scenarios_passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
