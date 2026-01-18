"""
Unit tests for the Intelligent Interruption Filter.

These tests verify that the filter correctly:
1. Ignores backchanneling words when the agent is speaking
2. Allows all words when the agent is silent
3. Detects command words that should always interrupt
4. Handles mixed inputs containing both backchanneling and command words
"""

import pytest

from livekit.agents.voice.interrupt_filter import (
    InterruptFilter,
    InterruptFilterConfig,
    DEFAULT_BACKCHANNELING_WORDS,
    DEFAULT_INTERRUPT_WORDS,
    _normalize_text,
    _split_into_words,
)


class TestInterruptFilter:
    """Tests for the InterruptFilter class."""

    def setup_method(self):
        """Set up a fresh filter for each test."""
        self.filter = InterruptFilter()

    # ==========================================
    # Test 1: Backchanneling ignored when speaking
    # ==========================================

    @pytest.mark.parametrize(
        "transcript",
        [
            "yeah",
            "Yeah",
            "YEAH",
            "ok",
            "okay",
            "OK",
            "hmm",
            "uh-huh",
            "uh huh",
            "mhm",
            "mm-hmm",
            "right",
            "aha",
            "ah",
            "oh",
            "i see",
            "sure",
            "gotcha",
            "got it",
            "alright",
            "all right",
            "cool",
            "nice",
            "great",
            "good",
            "indeed",
            "absolutely",
            "exactly",
            "totally",
            "definitely",
            "certainly",
            "of course",
            "true",
            "yep",
            "yes",
            "yup",
        ],
    )
    def test_backchanneling_ignored_while_speaking(self, transcript: str):
        """Backchanneling words should NOT interrupt when agent is speaking."""
        result = self.filter.should_interrupt(transcript, agent_is_speaking=True)
        assert result is False, f"'{transcript}' should be ignored while speaking"

    @pytest.mark.parametrize(
        "transcript",
        [
            "yeah yeah",
            "ok ok",
            "hmm hmm",
            "yeah ok",
            "right right",
            "uh-huh yeah",
            "okay cool",
            "yes yes",
            "mhm yeah",
        ],
    )
    def test_multiple_backchanneling_ignored_while_speaking(self, transcript: str):
        """Multiple backchanneling words should still be ignored."""
        result = self.filter.should_interrupt(transcript, agent_is_speaking=True)
        assert result is False, f"'{transcript}' should be ignored while speaking"

    # ==========================================
    # Test 2: All words processed when silent
    # ==========================================

    @pytest.mark.parametrize(
        "transcript",
        [
            "yeah",
            "ok",
            "hmm",
            "stop",
            "what about that",
            "tell me more",
            "yeah ok",
        ],
    )
    def test_all_words_processed_when_silent(self, transcript: str):
        """All words should trigger interrupt when agent is silent (processing them)."""
        result = self.filter.should_interrupt(transcript, agent_is_speaking=False)
        assert result is True, f"'{transcript}' should process when agent is silent"

    # ==========================================
    # Test 3: Command words always interrupt
    # ==========================================

    @pytest.mark.parametrize(
        "transcript",
        [
            "stop",
            "Stop",
            "STOP",
            "wait",
            "hold on",
            "hold up",
            "pause",
            "no",
            "nope",
            "cancel",
            "quiet",
            "shut up",
            "be quiet",
            "silence",
            "enough",
            "halt",
            "hang on",
            "one moment",
            "one second",
            "just a moment",
            "just a second",
            "question",
            "but",
            "however",
            "actually",
            "excuse me",
            "sorry",
            "let me",
            "can i",
            "may i",
            "i have",
            "i need",
            "i want",
        ],
    )
    def test_command_words_interrupt_while_speaking(self, transcript: str):
        """Command words should ALWAYS interrupt when agent is speaking."""
        result = self.filter.should_interrupt(transcript, agent_is_speaking=True)
        assert result is True, f"'{transcript}' should interrupt while speaking"

    # ==========================================
    # Test 4: Mixed input detection
    # ==========================================

    @pytest.mark.parametrize(
        "transcript",
        [
            "yeah wait a second",
            "ok but wait",
            "hmm stop please",
            "uh-huh actually",
            "right but i have a question",
            "yeah hold on",
            "ok stop",
            "yes but",
            "sure but wait",
            "ok can i ask something",
        ],
    )
    def test_mixed_input_with_command_interrupts(self, transcript: str):
        """Mixed input containing command words should interrupt."""
        result = self.filter.should_interrupt(transcript, agent_is_speaking=True)
        assert result is True, f"'{transcript}' should interrupt (contains command word)"

    @pytest.mark.parametrize(
        "transcript",
        [
            "what is the capital of france",
            "tell me about history",
            "can you explain that again",
            "I don't understand",
            "go on",
            "continue please",
        ],
    )
    def test_non_backchanneling_non_command_interrupts(self, transcript: str):
        """Non-backchanneling, non-command content should still interrupt."""
        result = self.filter.should_interrupt(transcript, agent_is_speaking=True)
        assert result is True, f"'{transcript}' should interrupt (real input)"

    # ==========================================
    # Test 5: Edge cases
    # ==========================================

    def test_empty_transcript_no_interrupt(self):
        """Empty transcript should not interrupt."""
        result = self.filter.should_interrupt("", agent_is_speaking=True)
        assert result is False

    def test_whitespace_only_no_interrupt(self):
        """Whitespace-only transcript should not interrupt."""
        result = self.filter.should_interrupt("   ", agent_is_speaking=True)
        assert result is False

    def test_disabled_filter_always_interrupts(self):
        """When filter is disabled, should always return True."""
        self.filter.enabled = False
        result = self.filter.should_interrupt("yeah", agent_is_speaking=True)
        assert result is True

    def test_punctuation_stripped(self):
        """Punctuation should be stripped for matching."""
        result = self.filter.should_interrupt("yeah!", agent_is_speaking=True)
        assert result is False

        result = self.filter.should_interrupt("ok.", agent_is_speaking=True)
        assert result is False

        result = self.filter.should_interrupt("hmm?", agent_is_speaking=True)
        assert result is False

    # ==========================================
    # Test 6: Configuration
    # ==========================================

    def test_custom_backchanneling_words(self):
        """Custom backchanneling words should work."""
        custom_filter = InterruptFilter(backchanneling_words=["foo", "bar", "baz"])

        # Custom words should be ignored
        assert custom_filter.should_interrupt("foo", agent_is_speaking=True) is False
        assert custom_filter.should_interrupt("bar", agent_is_speaking=True) is False

        # Default word "yeah" should now interrupt (not in custom list)
        # But wait, "yeah" might still be there... let's check
        # Actually, the custom list replaces the default
        result = custom_filter.should_interrupt("yeah", agent_is_speaking=True)
        # "yeah" is not explicit command, not in backchanneling, so it's treated as real input
        assert result is True

    def test_custom_interrupt_words(self):
        """Custom interrupt words should work."""
        custom_filter = InterruptFilter(interrupt_words=["freeze", "halt now"])

        # Custom words should interrupt
        assert custom_filter.should_interrupt("freeze", agent_is_speaking=True) is True
        assert custom_filter.should_interrupt("halt now", agent_is_speaking=True) is True

    def test_add_remove_backchanneling_word(self):
        """Adding and removing words should work."""
        self.filter.add_backchanneling_word("foobar")
        assert self.filter.should_interrupt("foobar", agent_is_speaking=True) is False

        self.filter.remove_backchanneling_word("foobar")
        assert self.filter.should_interrupt("foobar", agent_is_speaking=True) is True

    def test_add_remove_interrupt_word(self):
        """Adding and removing interrupt words should work."""
        self.filter.add_interrupt_word("emergency")
        assert self.filter.should_interrupt("emergency", agent_is_speaking=True) is True

        self.filter.remove_interrupt_word("emergency")
        # Now it's just a regular word, not backchanneling, so still interrupts
        assert self.filter.should_interrupt("emergency", agent_is_speaking=True) is True


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_normalize_text(self):
        """Test text normalization."""
        assert _normalize_text("  Hello World  ") == "hello world"
        assert _normalize_text("YEAH!") == "yeah"
        assert _normalize_text("ok.") == "ok"
        assert _normalize_text("  multiple   spaces  ") == "multiple spaces"

    def test_split_into_words(self):
        """Test word splitting."""
        assert _split_into_words("hello world") == ["hello", "world"]
        assert _split_into_words("  one   two  ") == ["one", "two"]
        assert _split_into_words("HELLO") == ["hello"]


class TestInterruptFilterConfig:
    """Tests for InterruptFilterConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = InterruptFilterConfig()
        assert config.enabled is True
        assert len(config.backchanneling_words) > 0
        assert len(config.interrupt_words) > 0
        assert config.case_sensitive is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = InterruptFilterConfig(
            enabled=False,
            backchanneling_words=["foo", "bar"],
            interrupt_words=["stop", "halt"],
            case_sensitive=True,
        )
        assert config.enabled is False
        assert config.backchanneling_words == ["foo", "bar"]
        assert config.interrupt_words == ["stop", "halt"]
        assert config.case_sensitive is True


class TestDefaultWordLists:
    """Tests for the default word lists."""

    def test_backchanneling_words_list_not_empty(self):
        """Default backchanneling words list should not be empty."""
        assert len(DEFAULT_BACKCHANNELING_WORDS) > 0

    def test_interrupt_words_list_not_empty(self):
        """Default interrupt words list should not be empty."""
        assert len(DEFAULT_INTERRUPT_WORDS) > 0

    def test_common_backchanneling_words_included(self):
        """Common backchanneling words should be in the default list."""
        common = ["yeah", "ok", "okay", "hmm", "uh-huh", "right", "sure"]
        for word in common:
            assert word in DEFAULT_BACKCHANNELING_WORDS, f"'{word}' should be in defaults"

    def test_common_interrupt_words_included(self):
        """Common interrupt words should be in the default list."""
        common = ["stop", "wait", "no", "hold on", "pause"]
        for word in common:
            assert word in DEFAULT_INTERRUPT_WORDS, f"'{word}' should be in defaults"


# Integration-style scenarios from the assignment
class TestAssignmentScenarios:
    """Tests based on the specific scenarios from the assignment."""

    def setup_method(self):
        """Set up a fresh filter for each test."""
        self.filter = InterruptFilter()

    def test_scenario_1_backchanneling_while_agent_explains(self):
        """
        Scenario 1: Agent is explaining something at length.
        User says "yeah", "ok", "hmm" to show they're listening.
        Expected: Agent continues without interruption.
        """
        agent_speaking = True

        # User says these while agent is talking
        backchannels = ["yeah", "ok", "hmm", "uh-huh", "right", "I see"]

        for phrase in backchannels:
            result = self.filter.should_interrupt(phrase, agent_is_speaking=agent_speaking)
            assert result is False, f"Agent shouldn't stop for '{phrase}'"

    def test_scenario_2_responding_to_yeah_when_silent(self):
        """
        Scenario 2: Agent finishes and goes silent.
        User says "Yeah" as an affirmation or to continue.
        Expected: Agent responds to the user.
        """
        agent_speaking = False

        result = self.filter.should_interrupt("Yeah", agent_is_speaking=agent_speaking)
        assert result is True, "Agent should respond to 'Yeah' when silent"

    def test_scenario_3_explicit_interrupt_while_speaking(self):
        """
        Scenario 3: Agent is speaking.
        User says "No stop" or "Wait a second".
        Expected: Agent stops immediately.
        """
        agent_speaking = True

        # Explicit stop commands
        commands = ["No stop", "wait a second", "stop", "wait", "hold on", "pause"]

        for cmd in commands:
            result = self.filter.should_interrupt(cmd, agent_is_speaking=agent_speaking)
            assert result is True, f"Agent should stop for '{cmd}'"

    def test_scenario_4_mixed_with_command_word(self):
        """
        Scenario 4: Agent is speaking.
        User says "Yeah okay but wait".
        Expected: Agent stops (because "wait" is present).
        """
        agent_speaking = True

        result = self.filter.should_interrupt("Yeah okay but wait", agent_is_speaking=agent_speaking)
        assert result is True, "Agent should stop for 'Yeah okay but wait'"

        # More examples of mixed input
        mixed = [
            "yeah wait a second",
            "ok but stop",
            "hmm actually",
            "right but i have a question",
        ]

        for phrase in mixed:
            result = self.filter.should_interrupt(phrase, agent_is_speaking=agent_speaking)
            assert result is True, f"Agent should stop for '{phrase}'"
