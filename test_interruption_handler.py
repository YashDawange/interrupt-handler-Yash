"""
Test script for Intelligent Interruption Handler

This script tests the core logic of the interruption handler without requiring
a full LiveKit setup.
"""

import sys
from pathlib import Path

# Add the livekit-agents to the path
agents_path = Path(__file__).parent / "livekit-agents"
sys.path.insert(0, str(agents_path))

# Import directly from the file
import importlib.util
spec = importlib.util.spec_from_file_location(
    "interruption_handler",
    agents_path / "livekit" / "agents" / "voice" / "interruption_handler.py"
)
interruption_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interruption_handler)

InterruptionConfig = interruption_handler.InterruptionConfig
InterruptionHandler = interruption_handler.InterruptionHandler


def test_scenario_1():
    """Test Scenario 1: Long Explanation - Agent speaking, user says backchanneling words"""
    print("\n" + "="*80)
    print("SCENARIO 1: Long Explanation")
    print("="*80)
    
    handler = InterruptionHandler()
    agent_state = "speaking"
    
    test_cases = [
        ("yeah", True),  # Should ignore
        ("ok", True),  # Should ignore
        ("hmm", True),  # Should ignore
        ("okay yeah", True),  # Should ignore (all ignore words)
        ("uh-huh right", True),  # Should ignore (all ignore words)
    ]
    
    for transcript, expected_ignore in test_cases:
        should_ignore = handler.should_ignore_transcript(transcript, agent_state)
        should_interrupt = handler.should_interrupt(transcript, agent_state)
        
        status = "✅ PASS" if should_ignore == expected_ignore else "❌ FAIL"
        print(f"{status} | Transcript: '{transcript}' | Agent: {agent_state}")
        print(f"        Should ignore: {should_ignore} (expected: {expected_ignore})")
        print(f"        Should interrupt: {should_interrupt} (expected: {not expected_ignore})")


def test_scenario_2():
    """Test Scenario 2: Passive Affirmation - Agent silent, user says 'yeah'"""
    print("\n" + "="*80)
    print("SCENARIO 2: Passive Affirmation")
    print("="*80)
    
    handler = InterruptionHandler()
    agent_state = "listening"
    
    test_cases = [
        ("yeah", False),  # Should NOT ignore when agent is silent
        ("ok", False),  # Should NOT ignore
        ("hmm", False),  # Should NOT ignore
    ]
    
    for transcript, expected_ignore in test_cases:
        should_ignore = handler.should_ignore_transcript(transcript, agent_state)
        should_interrupt = handler.should_interrupt(transcript, agent_state)
        
        status = "✅ PASS" if should_ignore == expected_ignore else "❌ FAIL"
        print(f"{status} | Transcript: '{transcript}' | Agent: {agent_state}")
        print(f"        Should ignore: {should_ignore} (expected: {expected_ignore})")
        print(f"        Should interrupt: {should_interrupt} (expected: {not expected_ignore})")


def test_scenario_3():
    """Test Scenario 3: Active Interruption - Agent speaking, user says 'stop'"""
    print("\n" + "="*80)
    print("SCENARIO 3: Active Interruption")
    print("="*80)
    
    handler = InterruptionHandler()
    agent_state = "speaking"
    
    test_cases = [
        ("stop", False),  # Should NOT ignore (should interrupt)
        ("wait", False),  # Should NOT ignore
        ("no", False),  # Should NOT ignore
        ("no stop", False),  # Should NOT ignore
    ]
    
    for transcript, expected_ignore in test_cases:
        should_ignore = handler.should_ignore_transcript(transcript, agent_state)
        should_interrupt = handler.should_interrupt(transcript, agent_state)
        
        status = "✅ PASS" if should_ignore == expected_ignore else "❌ FAIL"
        print(f"{status} | Transcript: '{transcript}' | Agent: {agent_state}")
        print(f"        Should ignore: {should_ignore} (expected: {expected_ignore})")
        print(f"        Should interrupt: {should_interrupt} (expected: {not expected_ignore})")


def test_scenario_4():
    """Test Scenario 4: Mixed Input - Agent speaking, user says 'yeah but wait'"""
    print("\n" + "="*80)
    print("SCENARIO 4: Mixed Input")
    print("="*80)
    
    handler = InterruptionHandler()
    agent_state = "speaking"
    
    test_cases = [
        ("yeah wait a second", False),  # Should NOT ignore (contains 'wait')
        ("yeah okay but wait", False),  # Should NOT ignore (contains 'but', 'wait')
        ("ok stop", False),  # Should NOT ignore (contains 'stop')
        ("hmm actually", False),  # Should NOT ignore (contains 'actually')
    ]
    
    for transcript, expected_ignore in test_cases:
        should_ignore = handler.should_ignore_transcript(transcript, agent_state)
        should_interrupt = handler.should_interrupt(transcript, agent_state)
        
        status = "✅ PASS" if should_ignore == expected_ignore else "❌ FAIL"
        print(f"{status} | Transcript: '{transcript}' | Agent: {agent_state}")
        print(f"        Should ignore: {should_ignore} (expected: {expected_ignore})")
        print(f"        Should interrupt: {should_interrupt} (expected: {not expected_ignore})")


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "="*80)
    print("EDGE CASES")
    print("="*80)
    
    handler = InterruptionHandler()
    
    test_cases = [
        ("", "speaking", False),  # Empty string
        ("   ", "speaking", False),  # Whitespace only
        ("YEAH", "speaking", True),  # Case insensitive (uppercase)
        ("Yeah", "speaking", True),  # Case insensitive (mixed)
        ("year", "speaking", False),  # Similar word but not in list
        ("yeah yeah yeah", "speaking", True),  # Repeated ignore word
        ("thinking", "thinking", False),  # Different agent state
    ]
    
    for transcript, agent_state, expected_ignore in test_cases:
        should_ignore = handler.should_ignore_transcript(transcript, agent_state)
        
        status = "✅ PASS" if should_ignore == expected_ignore else "❌ FAIL"
        print(f"{status} | Transcript: '{transcript}' | Agent: {agent_state}")
        print(f"        Should ignore: {should_ignore} (expected: {expected_ignore})")


def test_custom_config():
    """Test custom configuration"""
    print("\n" + "="*80)
    print("CUSTOM CONFIGURATION")
    print("="*80)
    
    # Custom config with only "yes" and "no" as ignore words
    custom_config = InterruptionConfig(
        ignore_words=["yes"],
        case_sensitive=True,
        enabled=True
    )
    handler = InterruptionHandler(custom_config)
    
    test_cases = [
        ("yes", "speaking", True),  # Should ignore (in custom list)
        ("YES", "speaking", False),  # Should NOT ignore (case sensitive)
        ("yeah", "speaking", False),  # Should NOT ignore (not in custom list)
    ]
    
    for transcript, agent_state, expected_ignore in test_cases:
        should_ignore = handler.should_ignore_transcript(transcript, agent_state)
        
        status = "✅ PASS" if should_ignore == expected_ignore else "❌ FAIL"
        print(f"{status} | Transcript: '{transcript}' | Agent: {agent_state}")
        print(f"        Should ignore: {should_ignore} (expected: {expected_ignore})")


def test_disabled_handler():
    """Test disabled handler"""
    print("\n" + "="*80)
    print("DISABLED HANDLER")
    print("="*80)
    
    disabled_config = InterruptionConfig(enabled=False)
    handler = InterruptionHandler(disabled_config)
    
    test_cases = [
        ("yeah", "speaking", False),  # Should NOT ignore (handler disabled)
        ("ok", "speaking", False),  # Should NOT ignore
    ]
    
    for transcript, agent_state, expected_ignore in test_cases:
        should_ignore = handler.should_ignore_transcript(transcript, agent_state)
        
        status = "✅ PASS" if should_ignore == expected_ignore else "❌ FAIL"
        print(f"{status} | Transcript: '{transcript}' | Agent: {agent_state}")
        print(f"        Should ignore: {should_ignore} (expected: {expected_ignore})")
        print(f"        Note: Handler is disabled, so all inputs should be processed")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("INTELLIGENT INTERRUPTION HANDLER TESTS")
    print("="*80)
    
    test_scenario_1()
    test_scenario_2()
    test_scenario_3()
    test_scenario_4()
    test_edge_cases()
    test_custom_config()
    test_disabled_handler()
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)


if __name__ == "__main__":
    main()
