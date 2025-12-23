"""
Unit tests for intelligent interruption handling.

Tests the InterruptionFilter class to ensure it correctly distinguishes
between backchannel feedback and real interruptions.
"""

import unittest
from livekit.agents.voice.interrupt_filter import InterruptionFilter


class TestInterruptionFilter(unittest.TestCase):
    """Test cases for InterruptionFilter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.filter = InterruptionFilter()

    def test_backchannel_ignored_when_agent_speaking(self):
        """Test that backchannel words are ignored when agent is speaking."""
        test_cases = [
            "yeah",
            "ok",
            "okay",
            "hmm",
            "mhm",
            "uh-huh",
            "right",
            "aha",
            "yep",
            "sure",
        ]

        for transcript in test_cases:
            with self.subTest(transcript=transcript):
                should_ignore = self.filter.should_ignore_transcript(
                    transcript=transcript,
                    agent_is_speaking=True,
                )
                self.assertTrue(
                    should_ignore,
                    f"Backchannel '{transcript}' should be ignored when agent is speaking"
                )

    def test_backchannel_not_ignored_when_agent_silent(self):
        """Test that backchannel words are processed when agent is silent."""
        test_cases = ["yeah", "ok", "hmm", "right"]

        for transcript in test_cases:
            with self.subTest(transcript=transcript):
                should_ignore = self.filter.should_ignore_transcript(
                    transcript=transcript,
                    agent_is_speaking=False,
                )
                self.assertFalse(
                    should_ignore,
                    f"Backchannel '{transcript}' should NOT be ignored when agent is silent"
                )

    def test_interruption_commands_not_ignored(self):
        """Test that interruption commands always cause interruption."""
        test_cases = [
            ("wait", True),
            ("stop", True),
            ("no", True),
            ("hold on", True),
            ("pause", True),
            ("but", True),
            ("however", True),
            ("wait", False),  # Also test when agent is silent
            ("stop", False),
        ]

        for transcript, agent_speaking in test_cases:
            with self.subTest(transcript=transcript, agent_speaking=agent_speaking):
                should_ignore = self.filter.should_ignore_transcript(
                    transcript=transcript,
                    agent_is_speaking=agent_speaking,
                )
                self.assertFalse(
                    should_ignore,
                    f"Interruption command '{transcript}' should NOT be ignored "
                    f"(agent_speaking={agent_speaking})"
                )

    def test_mixed_input_not_ignored(self):
        """Test that mixed input (backchannel + other words) causes interruption."""
        test_cases = [
            "yeah but wait",
            "ok I have a question",
            "hmm what about",
            "right but no",
            "yeah okay but stop",
        ]

        for transcript in test_cases:
            with self.subTest(transcript=transcript):
                should_ignore = self.filter.should_ignore_transcript(
                    transcript=transcript,
                    agent_is_speaking=True,
                )
                self.assertFalse(
                    should_ignore,
                    f"Mixed input '{transcript}' should NOT be ignored (contains non-backchannel)"
                )

    def test_pure_backchannel_sequence(self):
        """Test that multiple backchannel words in sequence are ignored."""
        test_cases = [
            "yeah ok",
            "hmm right",
            "uh-huh yeah",
            "ok sure gotcha",
        ]

        for transcript in test_cases:
            with self.subTest(transcript=transcript):
                should_ignore = self.filter.should_ignore_transcript(
                    transcript=transcript,
                    agent_is_speaking=True,
                )
                self.assertTrue(
                    should_ignore,
                    f"Pure backchannel sequence '{transcript}' should be ignored"
                )

    def test_case_insensitivity(self):
        """Test that filtering is case-insensitive."""
        test_cases = [
            "YEAH",
            "Ok",
            "HMM",
            "RiGhT",
            "WAIT",
            "Stop",
        ]

        for transcript in test_cases:
            with self.subTest(transcript=transcript):
                # Test both scenarios
                result = self.filter.should_ignore_transcript(
                    transcript=transcript,
                    agent_is_speaking=True,
                )
                # Should work regardless of case
                self.assertIsInstance(result, bool)

    def test_empty_transcript(self):
        """Test that empty transcripts are ignored."""
        test_cases = ["", "   ", "\t", "\n"]

        for transcript in test_cases:
            with self.subTest(transcript=repr(transcript)):
                should_ignore = self.filter.should_ignore_transcript(
                    transcript=transcript,
                    agent_is_speaking=True,
                )
                self.assertTrue(
                    should_ignore,
                    f"Empty transcript {repr(transcript)} should be ignored"
                )

    def test_unknown_words(self):
        """Test that unknown words (not backchannel or command) cause interruption."""
        test_cases = [
            "hello",
            "what",
            "how",
            "tell me",
            "explain",
        ]

        for transcript in test_cases:
            with self.subTest(transcript=transcript):
                should_ignore = self.filter.should_ignore_transcript(
                    transcript=transcript,
                    agent_is_speaking=True,
                )
                self.assertFalse(
                    should_ignore,
                    f"Unknown word '{transcript}' should NOT be ignored"
                )

    def test_custom_backchannel_words(self):
        """Test custom backchannel word configuration."""
        custom_backchannel = {"custom", "test"}
        filter_custom = InterruptionFilter(backchannel_words=custom_backchannel)

        # Custom word should be recognized
        should_ignore = filter_custom.should_ignore_transcript(
            transcript="custom",
            agent_is_speaking=True,
        )
        self.assertTrue(should_ignore)

        # Default word should NOT be recognized
        should_ignore = filter_custom.should_ignore_transcript(
            transcript="yeah",
            agent_is_speaking=True,
        )
        self.assertFalse(should_ignore)

    def test_custom_interruption_commands(self):
        """Test custom interruption command configuration."""
        custom_commands = {"custom_stop", "custom_pause"}
        filter_custom = InterruptionFilter(interruption_commands=custom_commands)

        # Custom command should be recognized
        should_ignore = filter_custom.should_ignore_transcript(
            transcript="custom_stop",
            agent_is_speaking=True,
        )
        self.assertFalse(should_ignore)

    def test_filter_reason(self):
        """Test that get_filter_reason provides useful explanations."""
        test_cases = [
            ("yeah", True, "backchannel"),
            ("wait", True, "command"),
            ("yeah but", True, "mixed"),
            ("hello", True, "mixed"),
            ("yeah", False, "not speaking"),
        ]

        for transcript, agent_speaking, expected_keyword in test_cases:
            with self.subTest(transcript=transcript):
                reason = self.filter.get_filter_reason(
                    transcript=transcript,
                    agent_is_speaking=agent_speaking,
                )
                self.assertIn(
                    expected_keyword.lower(),
                    reason.lower(),
                    f"Reason for '{transcript}' should mention '{expected_keyword}'"
                )


class TestScenarioIntegration(unittest.TestCase):
    """Integration tests simulating real conversation scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.filter = InterruptionFilter()

    def test_scenario_long_explanation(self):
        """
        Scenario 1: Agent giving long explanation, user provides backchannel feedback.
        Expected: Agent continues speaking.
        """
        agent_speaking = True
        user_inputs = ["yeah", "ok", "uh-huh", "right", "hmm"]

        for user_input in user_inputs:
            should_ignore = self.filter.should_ignore_transcript(
                transcript=user_input,
                agent_is_speaking=agent_speaking,
            )
            self.assertTrue(
                should_ignore,
                f"During long explanation, '{user_input}' should be ignored"
            )

    def test_scenario_waiting_response(self):
        """
        Scenario 2: Agent asks question and waits, user says "yeah".
        Expected: Agent processes as valid input.
        """
        agent_speaking = False
        user_input = "yeah"

        should_ignore = self.filter.should_ignore_transcript(
            transcript=user_input,
            agent_is_speaking=agent_speaking,
        )
        self.assertFalse(
            should_ignore,
            "When agent is silent, 'yeah' should be processed as valid input"
        )

    def test_scenario_user_interrupts(self):
        """
        Scenario 3: Agent speaking, user says "wait" or "stop".
        Expected: Agent stops immediately.
        """
        agent_speaking = True
        interruption_words = ["wait", "stop", "no", "hold on"]

        for word in interruption_words:
            should_ignore = self.filter.should_ignore_transcript(
                transcript=word,
                agent_is_speaking=agent_speaking,
            )
            self.assertFalse(
                should_ignore, 
                f"Interruption command '{word}' should cause immediate stop"
            )

    def test_scenario_mixed_input(self):
        """
        Scenario 4: Agent speaking, user provides mixed input.
        Expected: Agent stops (not pure backchannel).
        """
        agent_speaking = True
        mixed_inputs = [
            "yeah but wait",
            "ok I have a question",
            "right but can you",
        ]

        for user_input in mixed_inputs:
            should_ignore = self.filter.should_ignore_transcript(
                transcript=user_input,
                agent_is_speaking=agent_speaking,
            )
            self.assertFalse(
                should_ignore,
                f"Mixed input '{user_input}' should cause interruption"
            )


if __name__ == "__main__":
    unittest.main()
