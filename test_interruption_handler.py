"""
Test script for Intelligent Interruption Handler
Run this to verify the implementation works correctly
"""
import sys
import os

# Add the examples directory to path so we can import the handler
sys.path.append(os.path.join(os.getcwd(), 'examples', 'voice_agents'))

from interruption_handler import InterruptionHandler, SOFT_ACKNOWLEDGMENTS, HARD_INTERRUPTS

def test_soft_acknowledgments():
    """Test that soft acknowledgments are correctly identified"""
    print("Testing Soft Acknowledgments...")
    
    test_cases = [
        ("yeah", True),
        ("ok", True),
        ("hmm", True),
        ("yeah ok", True),
        ("uh huh", True),
        ("yeah but wait", False),  # Contains "but wait"
        ("tell me more", False),
    ]
    
    # Create a mock session
    class MockSession:
        agent_state = "speaking" # Simulate agent speaking
    
    handler = InterruptionHandler(MockSession(), setup_handlers=False)
    
    passed = 0
    
    for text, expected in test_cases:
        # Check logic: if it returns True for is_soft_ack, it means we should IGNORE interruption
        is_soft = handler._is_soft_acknowledgment(text.lower())
        is_hard = handler._is_hard_interrupt(text.lower())
        
        # Logic: It is a "Safe/Soft" interruption (Ignore) if soft=True and hard=False
        should_ignore = is_soft and not is_hard
        
        # For "yeah but wait": is_soft=False (because >3 words), is_hard=True. 
        # For "yeah": is_soft=True, is_hard=False.
        
        # We test _is_soft_acknowledgment directly first
        result = handler._is_soft_acknowledgment(text.lower())
        
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        print(f"  [{status}] Input: '{text}' -> Is Soft Ack? {result} (Expected: {expected})")
    
    print(f"Result: {passed}/{len(test_cases)} passed\n")
    return passed == len(test_cases)

def test_hard_interrupts():
    """Test that hard interrupts are correctly identified"""
    print("Testing Hard Interrupts...")
    
    test_cases = [
        ("wait", True),
        ("stop", True),
        ("no", True),
        ("wait a second", True),
        ("yeah", False),
    ]
    
    class MockSession:
        agent_state = "speaking"
    
    handler = InterruptionHandler(MockSession(), setup_handlers=False)
    
    passed = 0
    for text, expected in test_cases:
        result = handler._is_hard_interrupt(text.lower())
        status = "PASS" if result == expected else "FAIL"
        if result == expected: passed += 1
        print(f"  [{status}] Input: '{text}' -> Is Hard Interrupt? {result} (Expected: {expected})")
        
    print(f"Result: {passed}/{len(test_cases)} passed\n")
    return passed == len(test_cases)

if __name__ == "__main__":
    print("=== Intelligent Interruption Handler Verification Log ===\n")
    test_soft_acknowledgments()
    test_hard_interrupts()
    print("=== Verification Complete ===")
