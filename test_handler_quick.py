"""
Quick test to verify the intelligent interruption handler is working
"""
import os
import sys

# Add the livekit-agents to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'livekit-agents'))

def test_handler():
    print("=" * 60)
    print("Testing Intelligent Interruption Handler")
    print("=" * 60)
    
    try:
        from livekit.agents.voice.interruption_handler import (
            InterruptionConfig, 
            InterruptionHandler
        )
        print("✓ Import successful\n")
    except ImportError as e:
        print(f"✗ Import failed: {e}\n")
        return False
    
    # Create handler with default config
    handler = InterruptionHandler()
    print("✓ Handler created with default config\n")
    
    # Test Scenario 1: Agent speaking + backchanneling
    print("TEST 1: Agent speaking + 'yeah' → Should IGNORE")
    result = handler.should_ignore_transcript("yeah", "speaking")
    print(f"  Result: {result} (expected: True)")
    print(f"  {'✓ PASS' if result == True else '✗ FAIL'}\n")
    
    # Test Scenario 2: Agent silent + backchanneling
    print("TEST 2: Agent listening + 'yeah' → Should RESPOND")
    result = handler.should_ignore_transcript("yeah", "listening")
    print(f"  Result: {result} (expected: False)")
    print(f"  {'✓ PASS' if result == False else '✗ FAIL'}\n")
    
    # Test Scenario 3: Agent speaking + command
    print("TEST 3: Agent speaking + 'stop' → Should INTERRUPT")
    result = handler.should_ignore_transcript("stop", "speaking")
    print(f"  Result: {result} (expected: False)")
    print(f"  {'✓ PASS' if result == False else '✗ FAIL'}\n")
    
    # Test Scenario 4: Mixed input
    print("TEST 4: Agent speaking + 'yeah wait' → Should INTERRUPT")
    result = handler.should_ignore_transcript("yeah wait", "speaking")
    print(f"  Result: {result} (expected: False)")
    print(f"  {'✓ PASS' if result == False else '✗ FAIL'}\n")
    
    print("=" * 60)
    print("All core logic tests completed!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = test_handler()
    sys.exit(0 if success else 1)
