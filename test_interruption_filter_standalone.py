"""
Standalone unit tests for the Intelligent Interruption Filter.

This test file can be run directly without installing all dependencies:
    python test_interruption_filter_standalone.py

It tests only the filter logic by importing the module directly.
"""

import sys
from pathlib import Path

# Add the livekit-agents directory to the path
project_root = Path(__file__).parent
livekit_agents_path = project_root / "livekit-agents"
if livekit_agents_path.exists():
    sys.path.insert(0, str(livekit_agents_path))

# Import the filter file directly (it has no external dependencies)
import importlib.util
filter_path = livekit_agents_path / "livekit" / "agents" / "voice" / "interruption_filter.py"
if not filter_path.exists():
    raise FileNotFoundError(f"Filter file not found at {filter_path}")

spec = importlib.util.spec_from_file_location("livekit.agents.voice.interruption_filter", filter_path)
interruption_filter = importlib.util.module_from_spec(spec)
# Set up the module namespace properly
interruption_filter.__name__ = "livekit.agents.voice.interruption_filter"
interruption_filter.__package__ = "livekit.agents.voice"
sys.modules["livekit"] = type(sys)('livekit')
sys.modules["livekit.agents"] = type(sys)('livekit.agents')
sys.modules["livekit.agents.voice"] = type(sys)('livekit.agents.voice')
sys.modules["livekit.agents.voice.interruption_filter"] = interruption_filter
spec.loader.exec_module(interruption_filter)
InterruptionFilter = interruption_filter.InterruptionFilter
InterruptionFilterConfig = interruption_filter.InterruptionFilterConfig


def test_passive_words_while_speaking():
    """Passive words should NOT interrupt when agent is speaking."""
    filter = InterruptionFilter()
    
    passive_words = ["yeah", "ok", "hmm", "right", "uh-huh", "yep", "sure"]
    for word in passive_words:
        result = filter.should_interrupt(word, agent_is_speaking=True)
        assert result == False, f"'{word}' should not interrupt when agent is speaking"
        print(f"[PASS] '{word}' correctly ignored while speaking")


def test_interrupt_words_while_speaking():
    """Interrupt words SHOULD interrupt when agent is speaking."""
    filter = InterruptionFilter()
    
    interrupt_words = ["wait", "stop", "no", "hold on", "pause"]
    for word in interrupt_words:
        result = filter.should_interrupt(word, agent_is_speaking=True)
        assert result == True, f"'{word}' should interrupt when agent is speaking"
        print(f"[PASS] '{word}' correctly interrupts while speaking")


def test_passive_words_while_silent():
    """Passive words should be processed normally when agent is silent."""
    filter = InterruptionFilter()
    
    # When agent is silent, all input should be processed (should_interrupt=True means process it)
    passive_words = ["yeah", "ok", "hmm"]
    for word in passive_words:
        result = filter.should_interrupt(word, agent_is_speaking=False)
        assert result == True, f"'{word}' should be processed when agent is silent"
        print(f"[PASS] '{word}' correctly processed when agent is silent")


def test_mixed_input_with_interrupt_command():
    """Mixed input containing interrupt commands should interrupt."""
    filter = InterruptionFilter()
    
    mixed_inputs = [
        "yeah wait",
        "ok stop",
        "yeah okay but wait",
        "hmm no",
        "right but stop",
    ]
    
    for text in mixed_inputs:
        result = filter.should_interrupt(text, agent_is_speaking=True)
        assert result == True, f"'{text}' should interrupt because it contains interrupt commands"
        print(f"[PASS] '{text}' correctly interrupts (contains command)")


def test_mixed_input_only_passive():
    """Mixed input with only passive words should not interrupt."""
    filter = InterruptionFilter()
    
    mixed_passive = [
        "yeah ok",
        "hmm right",
        "ok yeah sure",
        "uh-huh yeah",
    ]
    
    for text in mixed_passive:
        result = filter.should_interrupt(text, agent_is_speaking=True)
        assert result == False, f"'{text}' should not interrupt (only passive words)"
        print(f"[PASS] '{text}' correctly ignored (only passive words)")


def test_case_insensitive():
    """Filter should be case-insensitive."""
    filter = InterruptionFilter()
    
    # Test various cases
    test_cases = [
        ("YEAH", False),
        ("Yeah", False),
        ("WAIT", True),
        ("Wait", True),
        ("wAiT", True),
    ]
    
    for text, expected in test_cases:
        result = filter.should_interrupt(text, agent_is_speaking=True)
        assert result == expected, f"Case-insensitive test failed for '{text}'"
    print("[PASS] Case-insensitive matching works correctly")


def test_filter_disabled():
    """When filter is disabled, should always interrupt."""
    config = InterruptionFilterConfig(enabled=False)
    filter = InterruptionFilter(config)
    
    # Even passive words should interrupt when filter is disabled
    result = filter.should_interrupt("yeah", agent_is_speaking=True)
    assert result == True
    print("[PASS] Filter disabled mode works correctly")


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("Testing Intelligent Interruption Filter")
    print("=" * 60)
    print()
    
    tests = [
        ("Passive words while speaking", test_passive_words_while_speaking),
        ("Interrupt words while speaking", test_interrupt_words_while_speaking),
        ("Passive words while silent", test_passive_words_while_silent),
        ("Mixed input with interrupt commands", test_mixed_input_with_interrupt_command),
        ("Mixed input only passive", test_mixed_input_only_passive),
        ("Case insensitive", test_case_insensitive),
        ("Filter disabled", test_filter_disabled),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n[{test_name}]")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[FAILURE] {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(run_all_tests())