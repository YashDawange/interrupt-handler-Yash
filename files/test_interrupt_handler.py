"""
Test script for Intelligent Interrupt Handler
Tests the core logic independently
"""

import asyncio
import logging
from interrupt_handler import IntelligentInterruptHandler, InterruptConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

logger = logging.getLogger("test")


async def run_tests():
    """Run comprehensive tests of interrupt handler logic"""
    
    # Create handler with test configuration
    config = InterruptConfig(
        ignore_words={'yeah', 'ok', 'hmm', 'uh-huh', 'right', 'mhm'},
        interrupt_words={'stop', 'wait', 'no', 'but'}
    )
    
    handler = IntelligentInterruptHandler(config)
    
    # Define test cases
    # Format: (agent_speaking, text, expected_result, description)
    test_cases = [
        # Scenario 1: The Long Explanation (Agent speaking + backchanneling)
        (True, "yeah", False, "Agent speaking + 'yeah' → IGNORE"),
        (True, "ok", False, "Agent speaking + 'ok' → IGNORE"),
        (True, "hmm", False, "Agent speaking + 'hmm' → IGNORE"),
        (True, "yeah ok hmm", False, "Agent speaking + multiple backchannels → IGNORE"),
        (True, "uh-huh right", False, "Agent speaking + 'uh-huh right' → IGNORE"),
        
        # Scenario 2: The Passive Affirmation (Agent silent + backchanneling)
        (False, "yeah", True, "Agent silent + 'yeah' → RESPOND"),
        (False, "ok", True, "Agent silent + 'ok' → RESPOND"),
        (False, "sure", True, "Agent silent + 'sure' → RESPOND"),
        
        # Scenario 3: The Correction (Agent speaking + interruption)
        (True, "stop", True, "Agent speaking + 'stop' → INTERRUPT"),
        (True, "wait", True, "Agent speaking + 'wait' → INTERRUPT"),
        (True, "no stop", True, "Agent speaking + 'no stop' → INTERRUPT"),
        
        # Scenario 4: The Mixed Input (Agent speaking + mixed phrase)
        (True, "yeah but wait", True, "Agent speaking + 'yeah but wait' → INTERRUPT (has 'but')"),
        (True, "ok wait", True, "Agent speaking + 'ok wait' → INTERRUPT (has 'wait')"),
        (True, "hmm actually no", True, "Agent speaking + mixed with 'no' → INTERRUPT"),
        
        # Additional edge cases
        (True, "what about this", True, "Agent speaking + substantive speech → PROCESS"),
        (False, "hello", True, "Agent silent + normal speech → RESPOND"),
        (True, "", True, "Empty string → PROCESS (safe default)"),
        (False, "stop", True, "Agent silent + 'stop' → RESPOND (normal command when silent)"),
    ]
    
    # Run tests
    print("\n" + "="*70)
    print("INTELLIGENT INTERRUPT HANDLER - TEST RESULTS")
    print("="*70)
    print()
    
    passed = 0
    failed = 0
    
    for agent_speaking, text, expected, description in test_cases:
        handler.set_agent_speaking(agent_speaking)
        result = await asyncio.coroutine(
            lambda: handler.should_process_speech(text, is_final=True)
        )()
        
        # Check if test passed
        if result == expected:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        # Print result
        print(f"{status} | {description}")
        print(f"      Agent: {'🗣️ Speaking' if agent_speaking else '🔇 Silent'} | "
              f"Input: '{text}' | Expected: {expected} | Got: {result}")
        
        # Show decision reasoning
        decision = handler.get_last_decision()
        if decision:
            action, reason = decision
            print(f"      Decision: {action} (reason: {reason})")
        
        print()
    
    # Summary
    print("="*70)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {failed} test(s) failed - review implementation")
    
    print("="*70)
    print()
    
    return failed == 0


async def test_scenario_walkthrough():
    """
    Interactive walkthrough of the key scenarios from the assignment
    """
    
    print("\n" + "="*70)
    print("SCENARIO WALKTHROUGHS")
    print("="*70)
    print()
    
    handler = IntelligentInterruptHandler()
    
    scenarios = [
        {
            "name": "Scenario 1: The Long Explanation",
            "context": "Agent is reading a long paragraph about history",
            "actions": [
                (True, "Okay..."),
                (True, "yeah..."),
                (True, "uh-huh"),
            ],
            "expected": "Agent continues speaking without interruption"
        },
        {
            "name": "Scenario 2: The Passive Affirmation",
            "context": "Agent asks 'Are you ready?' and goes silent",
            "actions": [
                (False, "Yeah"),
            ],
            "expected": "Agent processes 'Yeah' as an answer and proceeds"
        },
        {
            "name": "Scenario 3: The Correction",
            "context": "Agent is counting 'One, two, three...'",
            "actions": [
                (True, "No stop"),
            ],
            "expected": "Agent cuts off immediately"
        },
        {
            "name": "Scenario 4: The Mixed Input",
            "context": "Agent is speaking",
            "actions": [
                (True, "Yeah okay but wait"),
            ],
            "expected": "Agent stops (because 'but wait' triggers interruption)"
        }
    ]
    
    for scenario in scenarios:
        print(f"📋 {scenario['name']}")
        print(f"   Context: {scenario['context']}")
        print(f"   Expected: {scenario['expected']}")
        print()
        
        for agent_speaking, text in scenario['actions']:
            handler.set_agent_speaking(agent_speaking)
            result = handler.should_process_speech(text, is_final=True)
            
            action = "PROCESSES" if result else "IGNORES"
            icon = "✅" if result else "🔇"
            
            print(f"   {icon} User says: '{text}' → Agent {action}")
        
        print()
    
    print("="*70)
    print()


if __name__ == "__main__":
    print("\n🧪 Starting Intelligent Interrupt Handler Tests...\n")
    
    # Run unit tests
    success = asyncio.run(run_tests())
    
    # Run scenario walkthroughs
    asyncio.run(test_scenario_walkthrough())
    
    # Exit with appropriate code
    exit(0 if success else 1)
