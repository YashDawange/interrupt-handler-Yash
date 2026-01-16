"""
Unit tests for the Intelligent Interruption Filter.

Run with: python -m pytest test_interruption_filter.py -v
Or: python test_interruption_filter.py
"""

import sys
from pathlib import Path

# Add the livekit-agents directory to the path
project_root = Path(__file__).parent
livekit_agents_path = project_root / "livekit-agents"
if livekit_agents_path.exists():
    sys.path.insert(0, str(livekit_agents_path))

import pytest
from livekit.agents.voice.interruption_filter import InterruptionFilter, InterruptionFilterConfig


class TestInterruptionFilter:
    """Test suite for interruption filter logic."""

    def test_passive_words_while_speaking(self):
        """Passive words should NOT interrupt when agent is speaking."""
        filter = InterruptionFilter()
        
        passive_words = ["yeah", "ok", "hmm", "right", "uh-huh", "yep", "sure"]
        for word in passive_words:
            result = filter.should_interrupt(word, agent_is_speaking=True)
            assert result == False, f"'{word}' should not interrupt when agent is speaking"
            
            reason = filter.get_filter_reason(word, agent_is_speaking=True)
            assert reason == "passive_acknowledgement", f"Reason should be 'passive_acknowledgement' for '{word}'"

    def test_interrupt_words_while_speaking(self):
        """Interrupt words SHOULD interrupt when agent is speaking."""
        filter = InterruptionFilter()
        
        interrupt_words = ["wait", "stop", "no", "hold on", "pause"]
        for word in interrupt_words:
            result = filter.should_interrupt(word, agent_is_speaking=True)
            assert result == True, f"'{word}' should interrupt when agent is speaking"
            
            reason = filter.get_filter_reason(word, agent_is_speaking=True)
            assert reason == "contains_interrupt_command", f"Reason should be 'contains_interrupt_command' for '{word}'"

    def test_passive_words_while_silent(self):
        """Passive words should be processed normally when agent is silent."""
        filter = InterruptionFilter()
        
        # When agent is silent, all input should be processed (should_interrupt=True means process it)
        passive_words = ["yeah", "ok", "hmm"]
        for word in passive_words:
            result = filter.should_interrupt(word, agent_is_speaking=False)
            assert result == True, f"'{word}' should be processed when agent is silent"
            
            reason = filter.get_filter_reason(word, agent_is_speaking=False)
            assert reason == "agent_silent", f"Reason should be 'agent_silent' for '{word}' when agent is not speaking"

    def test_mixed_input_with_interrupt_command(self):
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
            
            reason = filter.get_filter_reason(text, agent_is_speaking=True)
            assert reason == "contains_interrupt_command", f"Reason should be 'contains_interrupt_command' for '{text}'"

    def test_mixed_input_only_passive(self):
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
            
            reason = filter.get_filter_reason(text, agent_is_speaking=True)
            assert reason == "passive_acknowledgement", f"Reason should be 'passive_acknowledgement' for '{text}'"

    def test_empty_transcript(self):
        """Empty transcript should not interrupt."""
        filter = InterruptionFilter()
        
        result = filter.should_interrupt("", agent_is_speaking=True)
        assert result == False
        
        result = filter.should_interrupt("   ", agent_is_speaking=True)
        assert result == False

    def test_filter_disabled(self):
        """When filter is disabled, should always interrupt."""
        config = InterruptionFilterConfig(enabled=False)
        filter = InterruptionFilter(config)
        
        # Even passive words should interrupt when filter is disabled
        result = filter.should_interrupt("yeah", agent_is_speaking=True)
        assert result == True
        
        reason = filter.get_filter_reason("yeah", agent_is_speaking=True)
        assert reason == "filter_disabled"

    def test_custom_config(self):
        """Test with custom configuration."""
        config = InterruptionFilterConfig(
            passive_words=["custom_passive"],
            interrupt_words=["custom_interrupt"],
            enabled=True,
        )
        filter = InterruptionFilter(config)
        
        # Custom passive word should not interrupt
        result = filter.should_interrupt("custom_passive", agent_is_speaking=True)
        assert result == False
        
        # Custom interrupt word should interrupt
        result = filter.should_interrupt("custom_interrupt", agent_is_speaking=True)
        assert result == True
        
        # Default words should not be recognized
        result = filter.should_interrupt("yeah", agent_is_speaking=True)
        assert result == True  # Not in custom config, so treated as normal input

    def test_case_insensitive(self):
        """Filter should be case-insensitive."""
        filter = InterruptionFilter()
        
        # Test various cases
        test_cases = [
            ("YEAH", False),
            ("Yeah", False),
            ("YEAH", False),
            ("WAIT", True),
            ("Wait", True),
            ("wAiT", True),
        ]
        
        for text, expected in test_cases:
            result = filter.should_interrupt(text, agent_is_speaking=True)
            assert result == expected, f"Case-insensitive test failed for '{text}'"

    def test_normal_input_while_speaking(self):
        """Normal input (not passive, not interrupt) should interrupt."""
        filter = InterruptionFilter()
        
        normal_inputs = [
            "hello",
            "what is that",
            "tell me more",
            "I have a question",
        ]
        
        for text in normal_inputs:
            result = filter.should_interrupt(text, agent_is_speaking=True)
            assert result == True, f"'{text}' should interrupt (normal input)"
            
            reason = filter.get_filter_reason(text, agent_is_speaking=True)
            assert reason == "valid_input", f"Reason should be 'valid_input' for '{text}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])