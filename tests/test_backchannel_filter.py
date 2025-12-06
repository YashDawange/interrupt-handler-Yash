"""
Tests for BackchannelFilter - Intelligent Interruption Handling.

These tests verify all 4 scenarios from the challenge:
1. Agent speaking + user says "yeah/ok/hmm" → IGNORE (agent continues)
2. Agent silent + user says "yeah" → RESPOND (process as input)
3. Agent speaking + user says "stop/no" → INTERRUPT (agent stops)
4. Agent speaking + user says "yeah okay but wait" → INTERRUPT (mixed input)
"""

import pytest

from livekit.agents.voice.backchannel_filter import BackchannelConfig, BackchannelFilter


class TestBackchannelFilter:
    """Test the core filtering logic for all challenge scenarios."""

    def setup_method(self) -> None:
        """Initialize filter with default config for each test."""
        self.filter = BackchannelFilter()

    # ========== Scenario 1: The Long Explanation ==========
    # Agent is speaking + user says backchannel words → IGNORE

    def test_ignore_yeah_while_speaking(self) -> None:
        """Agent speaking + 'yeah' → should be ignored."""
        assert self.filter.should_ignore("yeah", agent_is_speaking=True) is True

    def test_ignore_ok_while_speaking(self) -> None:
        """Agent speaking + 'ok' → should be ignored."""
        assert self.filter.should_ignore("ok", agent_is_speaking=True) is True

    def test_ignore_okay_while_speaking(self) -> None:
        """Agent speaking + 'okay' → should be ignored."""
        assert self.filter.should_ignore("okay", agent_is_speaking=True) is True

    def test_ignore_hmm_while_speaking(self) -> None:
        """Agent speaking + 'hmm' → should be ignored."""
        assert self.filter.should_ignore("hmm", agent_is_speaking=True) is True

    def test_ignore_uh_huh_while_speaking(self) -> None:
        """Agent speaking + 'uh-huh' → should be ignored."""
        assert self.filter.should_ignore("uh-huh", agent_is_speaking=True) is True

    def test_ignore_multiple_backchannels_while_speaking(self) -> None:
        """Agent speaking + 'okay yeah' → should be ignored (all backchannel words)."""
        assert self.filter.should_ignore("okay yeah", agent_is_speaking=True) is True

    def test_ignore_mhm_while_speaking(self) -> None:
        """Agent speaking + 'mhm' → should be ignored."""
        assert self.filter.should_ignore("mhm", agent_is_speaking=True) is True

    def test_ignore_right_while_speaking(self) -> None:
        """Agent speaking + 'right' → should be ignored."""
        assert self.filter.should_ignore("right", agent_is_speaking=True) is True

    # ========== Scenario 2: The Passive Affirmation ==========
    # Agent is silent + user says anything → RESPOND (never ignore)

    def test_respond_to_yeah_while_silent(self) -> None:
        """Agent silent + 'yeah' → should NOT be ignored (process as input)."""
        assert self.filter.should_ignore("yeah", agent_is_speaking=False) is False

    def test_respond_to_ok_while_silent(self) -> None:
        """Agent silent + 'ok' → should NOT be ignored."""
        assert self.filter.should_ignore("ok", agent_is_speaking=False) is False

    def test_respond_to_hmm_while_silent(self) -> None:
        """Agent silent + 'hmm' → should NOT be ignored."""
        assert self.filter.should_ignore("hmm", agent_is_speaking=False) is False

    def test_respond_to_hello_while_silent(self) -> None:
        """Agent silent + 'hello' → should NOT be ignored."""
        assert self.filter.should_ignore("hello", agent_is_speaking=False) is False

    # ========== Scenario 3: The Correction ==========
    # Agent speaking + user says interrupt command → INTERRUPT (don't ignore)

    def test_interrupt_on_stop_while_speaking(self) -> None:
        """Agent speaking + 'stop' → should NOT be ignored (interrupt)."""
        assert self.filter.should_ignore("stop", agent_is_speaking=True) is False

    def test_interrupt_on_no_while_speaking(self) -> None:
        """Agent speaking + 'no' → should NOT be ignored (interrupt)."""
        assert self.filter.should_ignore("no", agent_is_speaking=True) is False

    def test_interrupt_on_wait_while_speaking(self) -> None:
        """Agent speaking + 'wait' → should NOT be ignored (interrupt)."""
        assert self.filter.should_ignore("wait", agent_is_speaking=True) is False

    def test_interrupt_on_no_stop_while_speaking(self) -> None:
        """Agent speaking + 'no stop' → should NOT be ignored (interrupt)."""
        assert self.filter.should_ignore("no stop", agent_is_speaking=True) is False

    def test_interrupt_on_hold_on_while_speaking(self) -> None:
        """Agent speaking + 'hold on' → should NOT be ignored (interrupt)."""
        assert self.filter.should_ignore("hold on", agent_is_speaking=True) is False

    # ========== Scenario 4: The Mixed Input ==========
    # Agent speaking + mixed backchannel + interrupt → INTERRUPT

    def test_interrupt_on_yeah_but_wait_while_speaking(self) -> None:
        """Agent speaking + 'yeah but wait' → should NOT be ignored (contains 'but')."""
        assert self.filter.should_ignore("yeah but wait", agent_is_speaking=True) is False

    def test_interrupt_on_ok_wait_a_second_while_speaking(self) -> None:
        """Agent speaking + 'ok wait a second' → should NOT be ignored (contains 'wait')."""
        assert self.filter.should_ignore("ok wait a second", agent_is_speaking=True) is False

    def test_interrupt_on_yeah_okay_but_wait_while_speaking(self) -> None:
        """Agent speaking + 'yeah okay but wait' → should NOT be ignored."""
        assert self.filter.should_ignore("yeah okay but wait", agent_is_speaking=True) is False

    def test_interrupt_on_hmm_actually_while_speaking(self) -> None:
        """Agent speaking + 'hmm actually' → should NOT be ignored (contains 'actually')."""
        assert self.filter.should_ignore("hmm actually", agent_is_speaking=True) is False

    # ========== Edge Cases ==========

    def test_empty_transcript_while_speaking(self) -> None:
        """Agent speaking + empty string → should NOT be ignored."""
        assert self.filter.should_ignore("", agent_is_speaking=True) is False

    def test_whitespace_transcript_while_speaking(self) -> None:
        """Agent speaking + whitespace → should NOT be ignored."""
        assert self.filter.should_ignore("   ", agent_is_speaking=True) is False

    def test_case_insensitive_backchannel(self) -> None:
        """Backchannel detection should be case-insensitive."""
        assert self.filter.should_ignore("YEAH", agent_is_speaking=True) is True
        assert self.filter.should_ignore("Yeah", agent_is_speaking=True) is True
        assert self.filter.should_ignore("YeAh", agent_is_speaking=True) is True

    def test_case_insensitive_interrupt(self) -> None:
        """Interrupt detection should be case-insensitive."""
        assert self.filter.should_ignore("STOP", agent_is_speaking=True) is False
        assert self.filter.should_ignore("Stop", agent_is_speaking=True) is False

    def test_unknown_word_while_speaking(self) -> None:
        """Agent speaking + unknown word → should NOT be ignored (could be real input)."""
        assert self.filter.should_ignore("banana", agent_is_speaking=True) is False

    def test_sentence_with_backchannel_prefix(self) -> None:
        """Agent speaking + sentence starting with backchannel → should NOT be ignored."""
        assert self.filter.should_ignore("yeah I need help", agent_is_speaking=True) is False


class TestBackchannelConfig:
    """Test the configurable word lists."""

    def test_custom_ignore_words(self) -> None:
        """Custom ignore words should work."""
        config = BackchannelConfig(ignore_words={"custom", "words"})
        filter = BackchannelFilter(config)
        
        assert filter.should_ignore("custom", agent_is_speaking=True) is True
        assert filter.should_ignore("words", agent_is_speaking=True) is True
        # Default words should NOT work with custom config
        assert filter.should_ignore("yeah", agent_is_speaking=True) is False

    def test_custom_interrupt_words(self) -> None:
        """Custom interrupt words should work."""
        config = BackchannelConfig(interrupt_words={"emergency", "urgent"})
        filter = BackchannelFilter(config)
        
        assert filter.should_ignore("emergency", agent_is_speaking=True) is False
        # Default interrupt words should NOT work with custom config
        # (but "stop" is still not in ignore words, so it won't be ignored either)

    def test_disabled_filter(self) -> None:
        """Disabled filter should never ignore anything."""
        config = BackchannelConfig(enabled=False)
        filter = BackchannelFilter(config)
        
        # Even backchannels should not be ignored when filter is disabled
        assert filter.should_ignore("yeah", agent_is_speaking=True) is False
        assert filter.should_ignore("ok", agent_is_speaking=True) is False

    def test_empty_ignore_words(self) -> None:
        """Empty ignore words list should never ignore anything."""
        config = BackchannelConfig(ignore_words=set())
        filter = BackchannelFilter(config)
        
        assert filter.should_ignore("yeah", agent_is_speaking=True) is False


class TestPublicMethods:
    """Test the public helper methods."""

    def setup_method(self) -> None:
        self.filter = BackchannelFilter()

    def test_contains_interrupt_command(self) -> None:
        """Test the public interrupt command checker."""
        assert self.filter.contains_interrupt_command("stop now") is True
        assert self.filter.contains_interrupt_command("wait a second") is True
        assert self.filter.contains_interrupt_command("yeah okay") is False

    def test_is_backchannel_only(self) -> None:
        """Test the public backchannel checker."""
        assert self.filter.is_backchannel_only("yeah") is True
        assert self.filter.is_backchannel_only("ok sure") is True
        assert self.filter.is_backchannel_only("yeah I need help") is False
