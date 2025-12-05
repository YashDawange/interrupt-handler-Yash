"""Tests for the intelligent interruption filter."""

import pytest

from livekit.agents.voice.interruption_filter import (
    DEFAULT_BACKCHANNEL_WORDS,
    DEFAULT_COMMAND_WORDS,
    InterruptionFilter,
)


class TestInterruptionFilter:
    """Test cases for InterruptionFilter."""
    
    def test_agent_not_speaking_always_interrupts(self):
        """When agent is not speaking, all input should be processed."""
        filter = InterruptionFilter()
        
        assert filter.should_interrupt("yeah", agent_is_speaking=False)
        assert filter.should_interrupt("stop", agent_is_speaking=False)
        assert filter.should_interrupt("hello there", agent_is_speaking=False)
    
    def test_backchannel_ignored_when_speaking(self):
        """Backchannel words should be ignored when agent is speaking."""
        filter = InterruptionFilter()
        
        # Single backchannel words
        assert not filter.should_interrupt("yeah", agent_is_speaking=True)
        assert not filter.should_interrupt("ok", agent_is_speaking=True)
        assert not filter.should_interrupt("hmm", agent_is_speaking=True)
        assert not filter.should_interrupt("uh-huh", agent_is_speaking=True)
        assert not filter.should_interrupt("right", agent_is_speaking=True)
        
        # Multiple backchannel words
        assert not filter.should_interrupt("yeah ok", agent_is_speaking=True)
        assert not filter.should_interrupt("ok yeah hmm", agent_is_speaking=True)
        assert not filter.should_interrupt("uh huh yeah", agent_is_speaking=True)
    
    def test_command_words_interrupt_when_speaking(self):
        """Command words should always interrupt."""
        filter = InterruptionFilter()
        
        assert filter.should_interrupt("stop", agent_is_speaking=True)
        assert filter.should_interrupt("wait", agent_is_speaking=True)
        assert filter.should_interrupt("no", agent_is_speaking=True)
        assert filter.should_interrupt("hold on", agent_is_speaking=True)
        assert filter.should_interrupt("pause", agent_is_speaking=True)
    
    def test_mixed_input_interrupts(self):
        """Mixed input (backchannel + command) should interrupt."""
        filter = InterruptionFilter()
        
        assert filter.should_interrupt("yeah wait", agent_is_speaking=True)
        assert filter.should_interrupt("ok but", agent_is_speaking=True)
        assert filter.should_interrupt("yeah wait a second", agent_is_speaking=True)
        assert filter.should_interrupt("hmm actually", agent_is_speaking=True)
    
    def test_other_input_interrupts(self):
        """Other input (not backchannel) should interrupt."""
        filter = InterruptionFilter()
        
        assert filter.should_interrupt("tell me more", agent_is_speaking=True)
        assert filter.should_interrupt("what about", agent_is_speaking=True)
        assert filter.should_interrupt("can you explain", agent_is_speaking=True)
        assert filter.should_interrupt("I have a question", agent_is_speaking=True)
    
    def test_case_insensitive(self):
        """Filter should be case-insensitive."""
        filter = InterruptionFilter()
        
        assert not filter.should_interrupt("YEAH", agent_is_speaking=True)
        assert not filter.should_interrupt("Ok", agent_is_speaking=True)
        assert not filter.should_interrupt("HMM", agent_is_speaking=True)
        assert filter.should_interrupt("STOP", agent_is_speaking=True)
        assert filter.should_interrupt("Wait", agent_is_speaking=True)
    
    def test_punctuation_handling(self):
        """Filter should handle punctuation correctly."""
        filter = InterruptionFilter()
        
        assert not filter.should_interrupt("yeah.", agent_is_speaking=True)
        assert not filter.should_interrupt("ok!", agent_is_speaking=True)
        assert not filter.should_interrupt("hmm...", agent_is_speaking=True)
        assert filter.should_interrupt("stop!", agent_is_speaking=True)
        assert filter.should_interrupt("wait.", agent_is_speaking=True)
    
    def test_empty_transcript(self):
        """Empty transcript should not interrupt."""
        filter = InterruptionFilter()
        
        assert not filter.should_interrupt("", agent_is_speaking=True)
        assert not filter.should_interrupt("   ", agent_is_speaking=True)
    
    def test_custom_backchannel_words(self):
        """Should support custom backchannel words."""
        filter = InterruptionFilter(
            backchannel_words={"custom", "word"},
            command_words={"stop"}
        )
        
        assert not filter.should_interrupt("custom", agent_is_speaking=True)
        assert not filter.should_interrupt("word", agent_is_speaking=True)
        assert filter.should_interrupt("yeah", agent_is_speaking=True)  # Not in custom list
    
    def test_custom_command_words(self):
        """Should support custom command words."""
        filter = InterruptionFilter(
            backchannel_words={"yeah"},
            command_words={"custom", "command"}
        )
        
        assert filter.should_interrupt("custom", agent_is_speaking=True)
        assert filter.should_interrupt("command", agent_is_speaking=True)
        assert not filter.should_interrupt("stop", agent_is_speaking=True)  # Not in custom list (but not backchannel either, so it interrupts)
    
    def test_disabled_filter(self):
        """When disabled, filter should always interrupt."""
        filter = InterruptionFilter(enabled=False)
        
        assert filter.should_interrupt("yeah", agent_is_speaking=True)
        assert filter.should_interrupt("ok", agent_is_speaking=True)
        assert filter.should_interrupt("hmm", agent_is_speaking=True)
    
    def test_add_remove_backchannel_words(self):
        """Should be able to add/remove backchannel words dynamically."""
        filter = InterruptionFilter()
        
        # Add a new backchannel word
        filter.add_backchannel_word("custom")
        assert not filter.should_interrupt("custom", agent_is_speaking=True)
        
        # Remove it
        filter.remove_backchannel_word("custom")
        assert filter.should_interrupt("custom", agent_is_speaking=True)
    
    def test_add_remove_command_words(self):
        """Should be able to add/remove command words dynamically."""
        filter = InterruptionFilter()
        
        # Add a new command word
        filter.add_command_word("custom")
        assert filter.should_interrupt("custom", agent_is_speaking=True)
        
        # Remove it
        filter.remove_command_word("custom")
        # After removal, if it's not a backchannel word, it still interrupts
        # because it's considered "other input"
        assert filter.should_interrupt("custom", agent_is_speaking=True)
    
    def test_scenario_long_explanation(self):
        """Scenario 1: Agent reading long paragraph, user says backchannel."""
        filter = InterruptionFilter()
        
        # User says various backchannel words while agent is talking
        assert not filter.should_interrupt("Okay", agent_is_speaking=True)
        assert not filter.should_interrupt("yeah", agent_is_speaking=True)
        assert not filter.should_interrupt("uh-huh", agent_is_speaking=True)
        assert not filter.should_interrupt("okay yeah uh-huh", agent_is_speaking=True)
    
    def test_scenario_passive_affirmation(self):
        """Scenario 2: Agent asks question and goes silent, user says 'yeah'."""
        filter = InterruptionFilter()
        
        # Agent is silent, user responds
        assert filter.should_interrupt("Yeah", agent_is_speaking=False)
    
    def test_scenario_correction(self):
        """Scenario 3: Agent is counting, user says 'No stop'."""
        filter = InterruptionFilter()
        
        # User wants to stop
        assert filter.should_interrupt("No stop", agent_is_speaking=True)
        assert filter.should_interrupt("No", agent_is_speaking=True)
        assert filter.should_interrupt("stop", agent_is_speaking=True)
    
    def test_scenario_mixed_input(self):
        """Scenario 4: Agent is speaking, user says 'Yeah okay but wait'."""
        filter = InterruptionFilter()
        
        # Mixed input with command word
        assert filter.should_interrupt("Yeah okay but wait", agent_is_speaking=True)
        assert filter.should_interrupt("yeah but", agent_is_speaking=True)
        assert filter.should_interrupt("ok wait", agent_is_speaking=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
