"""
Tests for the BackchannelingFilter

This module tests the backchanneling filter logic to ensure it correctly 
distinguishes between passive acknowledgments and active interruptions.
"""

import unittest

from livekit.agents.voice.backchanneling_filter import BackchannelingFilter


class TestBackchannelingFilter(unittest.TestCase):
    """Test cases for the BackchannelingFilter."""

    def setUp(self):
        """Set up test fixtures."""
        self.filter = BackchannelingFilter()

    def test_is_backchanneling_simple_words(self):
        """Test that simple backchanneling words are correctly identified."""
        backchanneling_words = [
            "yeah",
            "ok",
            "okay",
            "hmm",
            "uh-huh",
            "uh huh",
            "right",
            "yep",
            "yup",
            "mm",
            "aha",
        ]

        for word in backchanneling_words:
            with self.subTest(word=word):
                self.assertTrue(
                    self.filter.is_backchanneling(word),
                    f"'{word}' should be identified as backchanneling",
                )

    def test_is_backchanneling_with_punctuation(self):
        """Test that backchanneling words with punctuation are correctly identified."""
        self.assertTrue(self.filter.is_backchanneling("yeah."))
        self.assertTrue(self.filter.is_backchanneling("ok!"))
        self.assertTrue(self.filter.is_backchanneling("hmm?"))
        self.assertTrue(self.filter.is_backchanneling("uh-huh,"))

    def test_is_backchanneling_multiple_words(self):
        """Test that multiple backchanneling words together are identified."""
        self.assertTrue(self.filter.is_backchanneling("yeah okay"))
        self.assertTrue(self.filter.is_backchanneling("uh huh right"))
        self.assertTrue(self.filter.is_backchanneling("mm hmm aha"))

    def test_is_not_backchanneling_with_commands(self):
        """Test that command words are not identified as backchanneling."""
        self.assertFalse(self.filter.is_backchanneling("stop"))
        self.assertFalse(self.filter.is_backchanneling("wait"))
        self.assertFalse(self.filter.is_backchanneling("no"))
        self.assertFalse(self.filter.is_backchanneling("don't"))

    def test_is_not_backchanneling_mixed(self):
        """Test that mixed sentences with commands are not identified as backchanneling."""
        self.assertFalse(self.filter.is_backchanneling("yeah but wait"))
        self.assertFalse(self.filter.is_backchanneling("ok no"))
        self.assertFalse(self.filter.is_backchanneling("hmm hold on"))

    def test_contains_command(self):
        """Test that command keywords are correctly identified."""
        command_words = [
            "stop",
            "wait",
            "hold",
            "pause",
            "no",
            "nope",
            "don't",
            "repeat",
            "but",
        ]

        for word in command_words:
            with self.subTest(word=word):
                self.assertTrue(
                    self.filter.contains_command(word),
                    f"'{word}' should be identified as a command",
                )

    def test_contains_command_in_sentence(self):
        """Test that command keywords are identified in sentences."""
        self.assertTrue(self.filter.contains_command("yeah but wait"))
        self.assertTrue(self.filter.contains_command("ok hold on"))
        self.assertTrue(self.filter.contains_command("no stop please"))

    def test_does_not_contain_command(self):
        """Test that sentences without commands are correctly identified."""
        self.assertFalse(self.filter.contains_command("yeah"))
        self.assertFalse(self.filter.contains_command("ok uh huh"))
        self.assertFalse(self.filter.contains_command("mm hmm"))

    def test_should_interrupt_agent_when_speaking_backchanneling(self):
        """Test that backchanneling does NOT interrupt agent when speaking."""
        # Agent is speaking, user says just backchanneling
        self.assertFalse(
            self.filter.should_interrupt_agent("yeah", agent_is_speaking=True)
        )
        self.assertFalse(
            self.filter.should_interrupt_agent("ok", agent_is_speaking=True)
        )
        self.assertFalse(
            self.filter.should_interrupt_agent("hmm", agent_is_speaking=True)
        )
        self.assertFalse(
            self.filter.should_interrupt_agent("uh huh right", agent_is_speaking=True)
        )

    def test_should_interrupt_agent_when_speaking_with_command(self):
        """Test that commands DO interrupt agent when speaking."""
        # Agent is speaking, user says command
        self.assertTrue(
            self.filter.should_interrupt_agent("stop", agent_is_speaking=True)
        )
        self.assertTrue(
            self.filter.should_interrupt_agent("wait", agent_is_speaking=True)
        )
        self.assertTrue(
            self.filter.should_interrupt_agent("no", agent_is_speaking=True)
        )
        self.assertTrue(
            self.filter.should_interrupt_agent(
                "yeah but wait", agent_is_speaking=True
            )
        )

    def test_should_interrupt_agent_when_silent_backchanneling(self):
        """Test that backchanneling DOES interrupt agent when silent (normal processing)."""
        # Agent is silent, user says backchanneling
        self.assertTrue(
            self.filter.should_interrupt_agent("yeah", agent_is_speaking=False)
        )
        self.assertTrue(
            self.filter.should_interrupt_agent("ok", agent_is_speaking=False)
        )

    def test_should_interrupt_agent_when_silent_with_command(self):
        """Test that commands DO interrupt agent when silent."""
        # Agent is silent, user says command
        self.assertTrue(
            self.filter.should_interrupt_agent("stop", agent_is_speaking=False)
        )
        self.assertTrue(
            self.filter.should_interrupt_agent("wait", agent_is_speaking=False)
        )

    def test_case_insensitive(self):
        """Test that the filter is case insensitive."""
        self.assertTrue(self.filter.is_backchanneling("YEAH"))
        self.assertTrue(self.filter.is_backchanneling("Yeah"))
        self.assertTrue(self.filter.is_backchanneling("YeAh"))
        self.assertTrue(self.filter.contains_command("STOP"))
        self.assertTrue(self.filter.contains_command("Stop"))

    def test_empty_text(self):
        """Test that empty text is handled correctly."""
        self.assertFalse(self.filter.is_backchanneling(""))
        self.assertFalse(self.filter.contains_command(""))
        self.assertFalse(self.filter.should_interrupt_agent("", agent_is_speaking=True))

    def test_custom_ignore_words(self):
        """Test that custom ignore words can be used."""
        custom_filter = BackchannelingFilter(ignore_words={"hello", "world"})
        self.assertTrue(custom_filter.is_backchanneling("hello"))
        self.assertTrue(custom_filter.is_backchanneling("world"))
        self.assertFalse(custom_filter.is_backchanneling("yeah"))

    def test_custom_command_keywords(self):
        """Test that custom command keywords can be used."""
        custom_filter = BackchannelingFilter(command_keywords={"abort", "cancel"})
        self.assertTrue(custom_filter.contains_command("abort"))
        self.assertTrue(custom_filter.contains_command("cancel"))
        self.assertFalse(custom_filter.contains_command("stop"))


class TestBackchannelingFilterScenarios(unittest.TestCase):
    """Test scenarios from the assignment."""

    def setUp(self):
        """Set up test fixtures."""
        self.filter = BackchannelingFilter()

    def test_scenario_1_long_explanation(self):
        """
        Scenario 1: The Long Explanation
        Context: Agent is reading a long paragraph about history.
        User Action: User says "Okay... yeah... uh-huh" while Agent is talking.
        Result: Agent audio does not break. It ignores the user input completely.
        """
        agent_is_speaking = True
        user_inputs = ["Okay", "yeah", "uh-huh"]

        for user_input in user_inputs:
            with self.subTest(user_input=user_input):
                # Should NOT interrupt
                self.assertFalse(
                    self.filter.should_interrupt_agent(user_input, agent_is_speaking)
                )

    def test_scenario_2_passive_affirmation(self):
        """
        Scenario 2: The Passive Affirmation
        Context: Agent asks "Are you ready?" and goes silent.
        User Action: User says "Yeah."
        Result: Agent processes "Yeah" as an answer and proceeds.
        """
        agent_is_speaking = False
        user_input = "Yeah"

        # Should allow interruption (normal conversational behavior)
        self.assertTrue(
            self.filter.should_interrupt_agent(user_input, agent_is_speaking)
        )

    def test_scenario_3_correction(self):
        """
        Scenario 3: The Correction
        Context: Agent is counting "One, two, three..."
        User Action: User says "No stop."
        Result: Agent cuts off immediately.
        """
        agent_is_speaking = True
        user_input = "No stop"

        # Should interrupt because "stop" is a command
        self.assertTrue(
            self.filter.should_interrupt_agent(user_input, agent_is_speaking)
        )

    def test_scenario_4_mixed_input(self):
        """
        Scenario 4: The Mixed Input
        Context: Agent is speaking.
        User Action: User says "Yeah okay but wait."
        Result: Agent stops (because "but wait" is not in the ignore list).
        """
        agent_is_speaking = True
        user_input = "Yeah okay but wait"

        # Should interrupt because "but wait" contains commands
        self.assertTrue(
            self.filter.should_interrupt_agent(user_input, agent_is_speaking)
        )


if __name__ == "__main__":
    unittest.main()
