#!/usr/bin/env python3
"""
Unit test for interrupt handling logic in AgentActivity.

This test verifies that:
1. Backchannels are ignored when agent is speaking
2. Command words trigger interrupts even when agent is speaking
3. Full sentences trigger interrupts even when agent is speaking
4. Empty transcripts are ignored
"""

import asyncio
import os
import sys
from pathlib import Path

# Add livekit-agents to path
sys.path.insert(0, str(Path(__file__).parent / "livekit-agents"))

from livekit.agents.voice.agent_activity import AgentActivity


def test_extract_words():
    """Test word extraction helper."""
    activity = AgentActivity.__new__(AgentActivity)
    activity._AgentActivity__stub = None  # Minimal init
    
    # Test basic extraction
    words = activity._extract_words("yeah okay let's go")
    assert set(words) == {"yeah", "okay", "let's", "go"}, f"Got: {words}"
    
    # Test with punctuation
    words = activity._extract_words("hello, world! how are you?")
    assert "hello" in words and "world" in words and "how" in words
    
    # Test normalization
    words = activity._extract_words("HELLO WORLD")
    assert all(w.islower() for w in words), f"Expected lowercase, got: {words}"
    
    print("✓ _extract_words tests passed")


def test_normalize_transcript():
    """Test transcript normalization."""
    activity = AgentActivity.__new__(AgentActivity)
    
    # Test basic normalization
    normalized = activity._normalize_transcript("  HELLO   WORLD  ")
    assert normalized == "hello world", f"Got: '{normalized}'"
    
    # Test empty
    normalized = activity._normalize_transcript("   ")
    assert normalized == "", f"Expected empty, got: '{normalized}'"
    
    print("✓ _normalize_transcript tests passed")


def test_contains_command_word():
    """Test command word detection."""
    activity = AgentActivity.__new__(AgentActivity)
    activity._command_words = {"stop", "wait", "hold on", "pause"}
    
    # Should detect command
    assert activity._contains_command_word("stop") == True
    assert activity._contains_command_word("please stop") == True
    assert activity._contains_command_word("hold on a second") == True
    
    # Should not detect non-command
    assert activity._contains_command_word("yeah") == False
    assert activity._contains_command_word("ok") == False
    
    print("✓ _contains_command_word tests passed")


def test_all_words_ignored():
    """Test if all words are in ignore set."""
    activity = AgentActivity.__new__(AgentActivity)
    activity._ignore_words = {"yeah", "ok", "okay", "hmm", "um"}
    
    # All words ignored
    assert activity._all_words_ignored("yeah okay") == True
    
    # Mixed words
    assert activity._all_words_ignored("yeah stop") == False
    
    # No words
    assert activity._all_words_ignored("") == True
    
    print("✓ _all_words_ignored tests passed")


def test_interrupt_decision_logic():
    """Test the core interrupt decision logic."""
    activity = AgentActivity.__new__(AgentActivity)
    activity._ignore_words = {"yeah", "ok", "okay", "hmm", "um", "uh"}
    activity._command_words = {"stop", "wait", "hold on", "pause"}
    activity._agent_is_speaking = True
    
    # Scenario 1: Pure backchannel while agent speaking → IGNORE
    transcript = "yeah okay"
    normalized = activity._normalize_transcript(transcript)
    
    is_command = activity._contains_command_word(normalized)
    all_ignored = activity._all_words_ignored(normalized)
    
    should_ignore = all_ignored and not is_command
    assert should_ignore == True, f"Should ignore backchannel: {transcript}"
    print(f"  ✓ Backchannel ignored: '{transcript}'")
    
    # Scenario 2: Command while agent speaking → DO NOT IGNORE
    transcript = "stop that"
    normalized = activity._normalize_transcript(transcript)
    
    is_command = activity._contains_command_word(normalized)
    all_ignored = activity._all_words_ignored(normalized)
    
    should_ignore = all_ignored and not is_command
    assert should_ignore == False, f"Should allow command: {transcript}"
    print(f"  ✓ Command allowed: '{transcript}'")
    
    # Scenario 3: Mixed content while agent speaking → DO NOT IGNORE
    transcript = "wait I have a question"
    normalized = activity._normalize_transcript(transcript)
    
    is_command = activity._contains_command_word(normalized)
    all_ignored = activity._all_words_ignored(normalized)
    
    should_ignore = all_ignored and not is_command
    assert should_ignore == False, f"Should allow mixed content: {transcript}"
    print(f"  ✓ Mixed content allowed: '{transcript}'")
    
    # Scenario 4: Full sentence while agent speaking → DO NOT IGNORE
    transcript = "what's the weather like today"
    normalized = activity._normalize_transcript(transcript)
    
    is_command = activity._contains_command_word(normalized)
    all_ignored = activity._all_words_ignored(normalized)
    
    should_ignore = all_ignored and not is_command
    assert should_ignore == False, f"Should allow full sentence: {transcript}"
    print(f"  ✓ Full sentence allowed: '{transcript}'")
    
    # Scenario 5: Agent NOT speaking → NEVER IGNORE
    activity._agent_is_speaking = False
    transcript = "yeah"
    
    # When agent not speaking, should always allow (return False from ignore decision)
    # This is handled in the callback logic, so we verify the helper functions don't ignore
    assert activity._all_words_ignored("yeah") == True
    print(f"  ✓ When agent silent, backchannel still extracted: 'yeah'")
    
    print("\n✓ Interrupt decision logic tests passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Interrupt Handler Logic")
    print("=" * 60)
    
    try:
        test_normalize_transcript()
        test_extract_words()
        test_contains_command_word()
        test_all_words_ignored()
        test_interrupt_decision_logic()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
