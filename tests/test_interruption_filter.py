"""
Unit tests for the Intelligent Interruption Filter

Tests cover all four scenarios from the assignment:
1. Agent speaking + filler words -> NO interruption
2. Agent speaking + command words -> YES interruption
3. Agent speaking + mixed input -> YES interruption (command takes precedence)
4. Agent silent + filler words -> YES processing (treated as valid input)
"""

import pytest

from livekit.agents.voice.interruption_filter import InterruptionFilter


class TestInterruptionFilter:
    """Test suite for InterruptionFilter"""

    def setup_method(self):
        """Initialize filter before each test"""
        self.filter = InterruptionFilter()

    def test_scenario_1_filler_while_speaking(self):
        """Scenario 1: Agent is speaking, user says filler words -> NO interruption"""
        test_cases = [
            "yeah",
            "ok",
            "okay",
            "hmm",
            "uh-huh",
            "mm-hmm",
            "right",
            "aha",
            "yeah yeah",
            "ok ok",
            "yeah hmm ok",
        ]

        for transcript in test_cases:
            decision = self.filter.should_interrupt(transcript, "speaking")
            assert (
                not decision.should_interrupt
            ), f"Should NOT interrupt for '{transcript}' while speaking"
            assert "filler" in decision.reason.lower() or "backchannel" in decision.reason.lower()

    def test_scenario_2_command_while_speaking(self):
        """Scenario 2: Agent is speaking, user says command words -> YES interruption"""
        test_cases = [
            "wait",
            "stop",
            "no",
            "hold on",
            "pause",
            "Wait a second",
            "Stop please",
            "No no no",
        ]

        for transcript in test_cases:
            decision = self.filter.should_interrupt(transcript, "speaking")
            assert (
                decision.should_interrupt
            ), f"SHOULD interrupt for '{transcript}' while speaking"
            assert "command" in decision.reason.lower() or "non-filler" in decision.reason.lower()

    def test_scenario_3_mixed_input_while_speaking(self):
        """Scenario 3: Agent is speaking, mixed input with command -> YES interruption"""
        test_cases = [
            "yeah wait a second",
            "ok but wait",
            "hmm actually no",
            "yeah okay but stop",
            "uh-huh however",
        ]

        for transcript in test_cases:
            decision = self.filter.should_interrupt(transcript, "speaking")
            assert (
                decision.should_interrupt
            ), f"SHOULD interrupt for mixed '{transcript}' with command"
            assert "command" in decision.reason.lower() or "non-filler" in decision.reason.lower()

    def test_scenario_4_filler_while_silent(self):
        """Scenario 4: Agent is silent, user says anything -> YES processing"""
        test_cases = [
            "yeah",
            "ok",
            "hmm",
            "wait",
            "hello",
            "tell me more",
        ]

        for transcript in test_cases:
            decision = self.filter.should_interrupt(transcript, "listening")
            assert (
                decision.should_interrupt
            ), f"SHOULD process '{transcript}' when agent is listening"
            assert "listening" in decision.reason.lower() or "normal" in decision.reason.lower()

    def test_empty_transcript(self):
        """Empty transcript should not interrupt"""
        decision = self.filter.should_interrupt("", "speaking")
        assert not decision.should_interrupt
        assert "empty" in decision.reason.lower()

    def test_whitespace_only(self):
        """Whitespace-only transcript should not interrupt"""
        decision = self.filter.should_interrupt("   ", "speaking")
        assert not decision.should_interrupt

    def test_punctuation_handling(self):
        """Filter should handle punctuation correctly"""
        test_cases = [
            ("yeah!", "speaking", False),
            ("ok?", "speaking", False),
            ("wait!", "speaking", True),
            ("stop.", "speaking", True),
        ]

        for transcript, state, should_int in test_cases:
            decision = self.filter.should_interrupt(transcript, state)
            assert decision.should_interrupt == should_int, f"Failed for '{transcript}'"

    def test_case_insensitivity(self):
        """Filter should be case-insensitive"""
        test_cases = [
            ("Yeah", "speaking", False),
            ("OKAY", "speaking", False),
            ("HMM", "speaking", False),
            ("WAIT", "speaking", True),
            ("Stop", "speaking", True),
        ]

        for transcript, state, should_int in test_cases:
            decision = self.filter.should_interrupt(transcript, state)
            assert (
                decision.should_interrupt == should_int
            ), f"Case sensitivity failed for '{transcript}'"

    def test_custom_ignore_list(self):
        """Test custom ignore list configuration"""
        custom_filter = InterruptionFilter(
            ignore_list=["yes", "sure", "gotcha"], command_list=["cancel", "undo"]
        )

        # Custom ignore words should work
        decision = custom_filter.should_interrupt("yes", "speaking")
        assert not decision.should_interrupt

        decision = custom_filter.should_interrupt("sure", "speaking")
        assert not decision.should_interrupt

        # Custom command words should work
        decision = custom_filter.should_interrupt("cancel", "speaking")
        assert decision.should_interrupt

        # Original defaults should NOT work since we replaced them
        decision = custom_filter.should_interrupt("yeah", "speaking")
        assert decision.should_interrupt  # "yeah" not in custom list

    def test_long_explanation_with_fillers(self):
        """Test that actual content triggers interruption even if it contains filler words"""
        # This should interrupt because it contains non-filler content
        transcript = "yeah I have a question about that"
        decision = self.filter.should_interrupt(transcript, "speaking")
        assert decision.should_interrupt, "Should interrupt for actual content"

    def test_multiple_fillers_in_sequence(self):
        """Test multiple filler words in sequence"""
        transcript = "yeah yeah okay hmm uh-huh"
        decision = self.filter.should_interrupt(transcript, "speaking")
        assert not decision.should_interrupt, "Should not interrupt for multiple fillers"

    def test_agent_thinking_state(self):
        """Test behavior when agent is in thinking state"""
        # When agent is thinking (not speaking), should process input
        decision = self.filter.should_interrupt("yeah", "thinking")
        assert decision.should_interrupt, "Should process input when agent is thinking"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
