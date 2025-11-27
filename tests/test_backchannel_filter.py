"""
Unit tests for backchannel filtering functionality.

Tests verify that the agent correctly distinguishes between:
1. Backchannel words (yeah, ok, hmm) that should be ignored while speaking
2. Real interruptions (wait, stop, no) that should stop the agent
3. State-aware behavior (responding to "yeah" when NOT speaking)
"""

import pytest
from livekit.agents.voice.backchannel_filter import (
    BackchannelConfig,
    BackchannelFilter,
    create_default_filter,
)


class TestBackchannelConfig:
    """Test backchannel configuration."""

    def test_default_config(self):
        """Test default configuration includes standard backchannel words."""
        config = BackchannelConfig()
        
        assert "yeah" in config.ignore_words
        assert "ok" in config.ignore_words
        assert "hmm" in config.ignore_words
        assert "right" in config.ignore_words
        assert "uh-huh" in config.ignore_words
        
        assert "wait" in config.interrupt_words
        assert "stop" in config.interrupt_words
        assert "no" in config.interrupt_words

    def test_custom_ignore_words(self):
        """Test custom ignore word configuration."""
        custom_words = {"custom1", "custom2"}
        config = BackchannelConfig(ignore_words=custom_words)
        
        assert config.ignore_words == custom_words
        assert "yeah" not in config.ignore_words  # Default not included

    def test_add_ignore_word(self):
        """Test adding words to ignore list."""
        config = BackchannelConfig()
        config.add_ignore_word("newword")
        
        assert "newword" in config.ignore_words

    def test_add_interrupt_word(self):
        """Test adding words to interrupt list."""
        config = BackchannelConfig()
        config.add_interrupt_word("emergency")
        
        assert "emergency" in config.interrupt_words

    def test_case_insensitive(self):
        """Test case-insensitive word matching."""
        config = BackchannelConfig(case_sensitive=False)
        config.add_ignore_word("TestWord")
        
        assert "testword" in config.ignore_words


class TestBackchannelFilter:
    """Test backchannel filtering logic."""

    def test_backchannel_only_detection(self):
        """Test detection of backchannel-only input."""
        filter = create_default_filter()
        
        # Single backchannel words
        assert filter.is_backchannel_only("yeah") is True
        assert filter.is_backchannel_only("ok") is True
        assert filter.is_backchannel_only("hmm") is True
        assert filter.is_backchannel_only("right") is True
        assert filter.is_backchannel_only("uh-huh") is True
        
        # Multiple backchannel words
        assert filter.is_backchannel_only("yeah yeah") is True
        assert filter.is_backchannel_only("ok right") is True

    def test_non_backchannel_detection(self):
        """Test detection of non-backchannel input."""
        filter = create_default_filter()
        
        # Real commands
        assert filter.is_backchannel_only("wait") is False
        assert filter.is_backchannel_only("stop") is False
        assert filter.is_backchannel_only("no") is False
        
        # Regular speech
        assert filter.is_backchannel_only("hello") is False
        assert filter.is_backchannel_only("tell me more") is False

    def test_mixed_sentence_detection(self):
        """Test detection of mixed sentences with backchannel + command."""
        filter = create_default_filter()
        
        # Backchannel + command should NOT be backchannel-only
        assert filter.is_backchannel_only("yeah wait a second") is False
        assert filter.is_backchannel_only("ok stop") is False
        assert filter.is_backchannel_only("hmm no") is False
        
        # Should trigger interruption
        assert filter.contains_interrupt_word("yeah wait") is True
        assert filter.contains_interrupt_word("ok stop") is True

    def test_case_insensitive_matching(self):
        """Test case-insensitive word matching."""
        filter = create_default_filter()
        
        assert filter.is_backchannel_only("YEAH") is True
        assert filter.is_backchannel_only("Ok") is True
        assert filter.is_backchannel_only("HMM") is True
        assert filter.contains_interrupt_word("WAIT") is True

    def test_state_aware_behavior_agent_speaking(self):
        """Test filtering when agent IS speaking - should ignore backchannel."""
        filter = create_default_filter()
        agent_is_speaking = True
        
        # Backchannel while speaking -> IGNORE
        assert filter.should_ignore_input("yeah", agent_is_speaking) is True
        assert filter.should_ignore_input("ok", agent_is_speaking) is True
        assert filter.should_ignore_input("hmm", agent_is_speaking) is True
        
        # Real commands while speaking -> DON'T IGNORE (interrupt)
        assert filter.should_ignore_input("wait", agent_is_speaking) is False
        assert filter.should_ignore_input("stop", agent_is_speaking) is False
        assert filter.should_ignore_input("tell me more", agent_is_speaking) is False

    def test_state_aware_behavior_agent_silent(self):
        """Test filtering when agent is NOT speaking - never ignore."""
        filter = create_default_filter()
        agent_is_speaking = False
        
        # When agent is silent, nothing should be ignored
        assert filter.should_ignore_input("yeah", agent_is_speaking) is False
        assert filter.should_ignore_input("ok", agent_is_speaking) is False
        assert filter.should_ignore_input("hmm", agent_is_speaking) is False
        assert filter.should_ignore_input("wait", agent_is_speaking) is False
        assert filter.should_ignore_input("hello", agent_is_speaking) is False

    def test_classification(self):
        """Test input classification for logging/debugging."""
        filter = create_default_filter()
        
        # Agent speaking scenarios
        assert filter.classify_input("yeah", agent_is_speaking=True) == "IGNORE"
        assert filter.classify_input("wait", agent_is_speaking=True) == "INTERRUPT"
        assert filter.classify_input("hello", agent_is_speaking=True) == "INTERRUPT"
        
        # Agent silent scenarios
        assert filter.classify_input("yeah", agent_is_speaking=False) == "RESPOND"
        assert filter.classify_input("wait", agent_is_speaking=False) == "RESPOND"
        assert filter.classify_input("hello", agent_is_speaking=False) == "RESPOND"

    def test_empty_input(self):
        """Test handling of empty or whitespace input."""
        filter = create_default_filter()
        
        assert filter.is_backchannel_only("") is False
        assert filter.is_backchannel_only("   ") is False
        assert filter.should_ignore_input("", agent_is_speaking=True) is False

    def test_punctuation_handling(self):
        """Test that punctuation doesn't affect detection."""
        filter = create_default_filter()
        
        assert filter.is_backchannel_only("yeah.") is True
        assert filter.is_backchannel_only("ok!") is True
        assert filter.is_backchannel_only("hmm?") is True
        assert filter.contains_interrupt_word("wait!") is True

    def test_multi_word_phrases(self):
        """Test multi-word phrase detection."""
        filter = create_default_filter()
        
        # Multi-word backchannel phrases
        assert filter.is_backchannel_only("uh-huh") is True
        assert filter.is_backchannel_only("got it") is True
        
        # Multi-word interrupt phrases
        assert filter.contains_interrupt_word("hang on") is True
        assert filter.contains_interrupt_word("excuse me") is True

    def test_realistic_scenarios(self):
        """Test realistic user input scenarios."""
        filter = create_default_filter()
        
        # Scenario 1: User listening while agent speaks
        assert filter.should_ignore_input("yeah", agent_is_speaking=True) is True
        assert filter.should_ignore_input("uh-huh", agent_is_speaking=True) is True
        assert filter.should_ignore_input("mhmm", agent_is_speaking=True) is True
        
        # Scenario 2: User wants to interrupt
        assert filter.should_ignore_input("wait a second", agent_is_speaking=True) is False
        assert filter.should_ignore_input("hold on", agent_is_speaking=True) is False
        assert filter.should_ignore_input("stop please", agent_is_speaking=True) is False
        
        # Scenario 3: User responds when agent is silent
        assert filter.should_ignore_input("yeah I agree", agent_is_speaking=False) is False
        assert filter.should_ignore_input("ok let's do that", agent_is_speaking=False) is False
        
        # Scenario 4: Mixed input while agent speaks
        assert filter.should_ignore_input("yeah but wait", agent_is_speaking=True) is False

    def test_custom_configuration(self):
        """Test using custom backchannel word lists."""
        custom_config = BackchannelConfig(
            ignore_words={"custom1", "custom2"},
            interrupt_words={"custom_stop"}
        )
        filter = BackchannelFilter(custom_config)
        
        assert filter.is_backchannel_only("custom1") is True
        assert filter.is_backchannel_only("custom2") is True
        assert filter.is_backchannel_only("yeah") is False  # Default not included
        
        assert filter.contains_interrupt_word("custom_stop") is True
        assert filter.contains_interrupt_word("wait") is False  # Default not included


class TestBackchannelIntegration:
    """Integration tests for backchannel filtering with agent scenarios."""

    def test_continuous_backchannel(self):
        """Test continuous backchannel acknowledgments don't interrupt."""
        filter = create_default_filter()
        agent_is_speaking = True
        
        # User continuously acknowledging
        inputs = ["yeah", "uh-huh", "right", "ok", "mhmm"]
        
        for user_input in inputs:
            should_ignore = filter.should_ignore_input(user_input, agent_is_speaking)
            assert should_ignore is True, f"Failed to ignore '{user_input}'"

    def test_false_start_scenario(self):
        """Test scenario where VAD triggers before STT completes."""
        filter = create_default_filter()
        
        # VAD detects speech at t=50ms
        agent_is_speaking = True
        
        # STT completes at t=400ms with "yeah"
        transcription = "yeah"
        
        # Should be ignored - backchannel only
        assert filter.should_ignore_input(transcription, agent_is_speaking) is True

    def test_interruption_detection_latency(self):
        """Test that interruption detection works with partial transcripts."""
        filter = create_default_filter()
        agent_is_speaking = True
        
        # Partial transcripts as they arrive
        partial1 = "w"  # Not backchannel, not interrupt word yet
        partial2 = "wa"
        partial3 = "wait"  # Now it's clear it's an interrupt
        
        # Early partials might not match backchannel or interrupt
        assert filter.is_backchannel_only(partial1) is False
        assert filter.is_backchannel_only(partial2) is False
        
        # Final transcript should be detected as interrupt
        assert filter.contains_interrupt_word(partial3) is True
        assert filter.should_ignore_input(partial3, agent_is_speaking) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
