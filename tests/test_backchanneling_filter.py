"""
Tests for the BackchannelingFilter - Intelligent Interruption Handling

These tests verify the core logic matrix:
| User Input          | Agent State | Desired Behavior |
|---------------------|-------------|------------------|
| "Yeah / Ok / Hmm"   | Speaking    | IGNORE           |
| "Wait / Stop / No"  | Speaking    | INTERRUPT        |
| "Yeah / Ok / Hmm"   | Silent      | RESPOND          |
| "Start / Hello"     | Silent      | RESPOND          |
"""

import pytest

from livekit.agents.voice.backchanneling_filter import (
    BackchannelingConfig,
    BackchannelingFilter,
    DEFAULT_COMMAND_WORDS,
    DEFAULT_FILLER_WORDS,
)


class TestBackchannelingFilter:
    """Test suite for the BackchannelingFilter."""

    @pytest.fixture
    def default_filter(self) -> BackchannelingFilter:
        """Create a filter with default configuration."""
        return BackchannelingFilter()

    @pytest.fixture
    def custom_filter(self) -> BackchannelingFilter:
        """Create a filter with custom configuration."""
        config = BackchannelingConfig(
            filler_words=frozenset(["yeah", "ok", "hmm"]),
            command_words=frozenset(["stop", "wait", "no"]),
        )
        return BackchannelingFilter(config)

    # ==================== Scenario 1: Long Explanation ====================
    # Agent is speaking, user says filler words -> IGNORE

    @pytest.mark.parametrize(
        "filler_word",
        ["yeah", "ok", "okay", "hmm", "right", "uh-huh", "mhm", "yep", "sure"],
    )
    def test_ignore_filler_words_while_agent_speaking(
        self, default_filter: BackchannelingFilter, filler_word: str
    ):
        """Agent speaking + filler word = IGNORE (should_ignore returns True)."""
        assert default_filter.should_ignore_transcript(
            filler_word, agent_speaking=True
        ), f"'{filler_word}' should be ignored while agent is speaking"

    def test_ignore_multiple_filler_words_while_speaking(
        self, default_filter: BackchannelingFilter
    ):
        """Agent speaking + multiple filler words = IGNORE."""
        assert default_filter.should_ignore_transcript(
            "yeah yeah", agent_speaking=True
        )
        assert default_filter.should_ignore_transcript("ok ok ok", agent_speaking=True)
        assert default_filter.should_ignore_transcript(
            "yeah ok hmm", agent_speaking=True
        )

    def test_ignore_filler_with_hesitation(self, default_filter: BackchannelingFilter):
        """Agent speaking + filler with spacing = IGNORE."""
        assert default_filter.should_ignore_transcript(
            "uh huh", agent_speaking=True
        )

    # ==================== Scenario 2: Passive Affirmation ====================
    # Agent is silent, user says filler word -> RESPOND (don't ignore)

    @pytest.mark.parametrize("filler_word", ["yeah", "ok", "hmm", "sure", "yep"])
    def test_respond_to_filler_when_agent_silent(
        self, default_filter: BackchannelingFilter, filler_word: str
    ):
        """Agent silent + filler word = RESPOND (should_ignore returns False)."""
        assert not default_filter.should_ignore_transcript(
            filler_word, agent_speaking=False
        ), f"'{filler_word}' should NOT be ignored when agent is silent"

    # ==================== Scenario 3: The Correction ====================
    # Agent is speaking, user says command word -> INTERRUPT (don't ignore)

    @pytest.mark.parametrize(
        "command_word", ["stop", "wait", "no", "hold", "pause", "help"]
    )
    def test_interrupt_on_command_words_while_speaking(
        self, default_filter: BackchannelingFilter, command_word: str
    ):
        """Agent speaking + command word = INTERRUPT (should_ignore returns False)."""
        assert not default_filter.should_ignore_transcript(
            command_word, agent_speaking=True
        ), f"'{command_word}' should trigger interruption while agent is speaking"

    def test_interrupt_on_no_stop(self, default_filter: BackchannelingFilter):
        """'No stop' should interrupt the agent."""
        assert not default_filter.should_ignore_transcript("no stop", agent_speaking=True)

    # ==================== Scenario 4: Mixed Input ====================
    # Agent is speaking, user says filler + command -> INTERRUPT

    @pytest.mark.parametrize(
        "mixed_input",
        [
            "yeah wait",
            "ok but wait",
            "yeah okay but wait",
            "hmm actually",
            "ok but stop",
            "yeah what",
            "right but why",
        ],
    )
    def test_interrupt_on_mixed_input_with_command(
        self, default_filter: BackchannelingFilter, mixed_input: str
    ):
        """Agent speaking + mixed input with command = INTERRUPT."""
        assert not default_filter.should_ignore_transcript(
            mixed_input, agent_speaking=True
        ), f"'{mixed_input}' contains command word and should interrupt"

    # ==================== Case Sensitivity ====================

    def test_case_insensitive_by_default(self, default_filter: BackchannelingFilter):
        """Filter should be case-insensitive by default."""
        assert default_filter.should_ignore_transcript("YEAH", agent_speaking=True)
        assert default_filter.should_ignore_transcript("Yeah", agent_speaking=True)
        assert default_filter.should_ignore_transcript("yEaH", agent_speaking=True)

    def test_case_sensitive_mode(self):
        """Case-sensitive mode should distinguish cases."""
        config = BackchannelingConfig(
            filler_words=frozenset(["yeah"]),  # Only lowercase
            case_sensitive=True,
        )
        filter_instance = BackchannelingFilter(config)

        # Lowercase should be ignored
        assert filter_instance.should_ignore_transcript("yeah", agent_speaking=True)
        # Uppercase should NOT be ignored (not in list)
        assert not filter_instance.should_ignore_transcript("YEAH", agent_speaking=True)

    # ==================== Edge Cases ====================

    def test_empty_transcript(self, default_filter: BackchannelingFilter):
        """Empty transcript should be treated as filler (ignored when speaking)."""
        assert default_filter.should_ignore_transcript("", agent_speaking=True)
        assert not default_filter.should_ignore_transcript("", agent_speaking=False)

    def test_whitespace_only_transcript(self, default_filter: BackchannelingFilter):
        """Whitespace-only transcript should be treated as filler."""
        assert default_filter.should_ignore_transcript("   ", agent_speaking=True)

    def test_punctuation_handling(self, default_filter: BackchannelingFilter):
        """Filler words with punctuation should still be recognized."""
        # STT often adds punctuation to transcripts
        assert default_filter.should_ignore_transcript("Yeah.", agent_speaking=True)
        assert default_filter.should_ignore_transcript("Ok!", agent_speaking=True)
        assert default_filter.should_ignore_transcript("Hmm?", agent_speaking=True)
        assert default_filter.should_ignore_transcript(" Yeah. ", agent_speaking=True)
        assert default_filter.should_ignore_transcript("Yeah, ok.", agent_speaking=True)

    def test_punctuation_only_transcript(self, default_filter: BackchannelingFilter):
        """Punctuation-only transcript should be ignored while speaking."""
        assert default_filter.should_ignore_transcript("...", agent_speaking=True)
        assert default_filter.should_ignore_transcript("!", agent_speaking=True)

    def test_non_filler_non_command_input(self, default_filter: BackchannelingFilter):
        """Random input that's neither filler nor command should interrupt."""
        # "hello" is not a filler word, so it should trigger interruption
        assert not default_filter.should_ignore_transcript("hello", agent_speaking=True)
        assert not default_filter.should_ignore_transcript(
            "the weather is nice", agent_speaking=True
        )

    def test_disabled_filter(self):
        """Disabled filter should never ignore anything."""
        config = BackchannelingConfig(enabled=False)
        disabled_filter = BackchannelingFilter(config)
        
        # Even filler words shouldn't be ignored when filter is disabled
        assert not disabled_filter.should_ignore_transcript("yeah", agent_speaking=True)
        assert not disabled_filter.should_ignore_transcript("ok", agent_speaking=True)

    # ==================== Analyze Transcript ====================

    def test_analyze_transcript_filler_only(self, default_filter: BackchannelingFilter):
        """Analyze should correctly identify filler-only transcript."""
        from livekit.agents.voice.backchanneling_filter import BackchannelingResult
        result = default_filter.analyze_transcript("yeah ok", agent_speaking=True)
        assert result == BackchannelingResult.IGNORE

    def test_analyze_transcript_with_command(
        self, default_filter: BackchannelingFilter
    ):
        """Analyze should correctly identify transcript with command."""
        from livekit.agents.voice.backchanneling_filter import BackchannelingResult
        result = default_filter.analyze_transcript("yeah but wait", agent_speaking=True)
        assert result == BackchannelingResult.INTERRUPT

    # ==================== Multi-word Filler Phrases ====================

    def test_multiword_filler_phrases(self, default_filter: BackchannelingFilter):
        """Multi-word filler phrases from DEFAULT_FILLER_WORDS should be recognized."""
        # These are actual multi-word phrases in DEFAULT_FILLER_WORDS
        assert default_filter.should_ignore_transcript("uh huh", agent_speaking=True)
        assert default_filter.should_ignore_transcript("mm hmm", agent_speaking=True)
        assert default_filter.should_ignore_transcript("got it", agent_speaking=True)
        assert default_filter.should_ignore_transcript("i see", agent_speaking=True)

    # ==================== Question Words ====================

    @pytest.mark.parametrize(
        "question_start", ["what", "why", "how", "when", "where", "who", "which"]
    )
    def test_question_words_trigger_interrupt(
        self, default_filter: BackchannelingFilter, question_start: str
    ):
        """Question words should trigger interruption."""
        assert not default_filter.should_ignore_transcript(
            question_start, agent_speaking=True
        ), f"'{question_start}' should trigger interruption (user asking question)"

    # ==================== Configuration ====================

    def test_custom_configuration(self):
        """Custom configuration should be respected."""
        config = BackchannelingConfig(
            filler_words=frozenset(["custom_filler"]),
            command_words=frozenset(["custom_command"]),
        )
        filter_instance = BackchannelingFilter(config)

        assert filter_instance.should_ignore_transcript(
            "custom_filler", agent_speaking=True
        )
        assert not filter_instance.should_ignore_transcript(
            "custom_command", agent_speaking=True
        )
        # Default words should NOT work with custom config
        assert not filter_instance.should_ignore_transcript("yeah", agent_speaking=True)

class TestDefaultWordLists:
    """Test the default word lists are comprehensive."""

    def test_default_filler_words_present(self):
        """Verify essential filler words are in the default list."""
        essential_fillers = ["yeah", "ok", "hmm", "right", "sure", "yep", "mhm"]
        for word in essential_fillers:
            assert (
                word in DEFAULT_FILLER_WORDS
            ), f"'{word}' should be in DEFAULT_FILLER_WORDS"

    def test_default_command_words_present(self):
        """Verify essential command words are in the default list."""
        essential_commands = ["stop", "wait", "no", "help", "what", "why", "how"]
        for word in essential_commands:
            assert (
                word in DEFAULT_COMMAND_WORDS
            ), f"'{word}' should be in DEFAULT_COMMAND_WORDS"

    def test_no_overlap_between_filler_and_command(self):
        """Filler and command word lists should not overlap."""
        overlap = DEFAULT_FILLER_WORDS & DEFAULT_COMMAND_WORDS
        assert (
            len(overlap) == 0
        ), f"Filler and command words overlap: {overlap}"


class TestEnvironmentConfiguration:
    """Test environment variable configuration."""

    def test_from_env_with_defaults(self, monkeypatch):
        """Config from env should use defaults when vars not set."""
        monkeypatch.delenv("BACKCHANNELING_ENABLED", raising=False)
        monkeypatch.delenv("BACKCHANNELING_FILLER_WORDS", raising=False)
        monkeypatch.delenv("BACKCHANNELING_COMMAND_WORDS", raising=False)

        config = BackchannelingConfig.from_env()
        
        assert config.enabled is True
        assert config.filler_words == DEFAULT_FILLER_WORDS
        assert config.command_words == DEFAULT_COMMAND_WORDS

    def test_from_env_disabled(self, monkeypatch):
        """Config from env should respect ENABLED=false."""
        monkeypatch.setenv("BACKCHANNELING_ENABLED", "false")
        
        config = BackchannelingConfig.from_env()
        assert config.enabled is False

    def test_from_env_custom_words(self, monkeypatch):
        """Config from env should parse custom word lists."""
        monkeypatch.setenv("BACKCHANNELING_FILLER_WORDS", "custom1,custom2")
        monkeypatch.setenv("BACKCHANNELING_COMMAND_WORDS", "cmd1,cmd2")
        
        config = BackchannelingConfig.from_env()
        
        assert config.filler_words == frozenset(["custom1", "custom2"])
        assert config.command_words == frozenset(["cmd1", "cmd2"])



