"""
Test cases for the Intelligent Interrupt Filter

Run with: python -m pytest test_interrupt_filter.py -v
Or simply: python test_interrupt_filter.py
"""

import unittest
from interrupt_filter import (
    InterruptFilter,
    InterruptFilterConfig,
    DEFAULT_IGNORE_WORDS,
    DEFAULT_INTERRUPT_WORDS,
)


class TestInterruptFilter(unittest.TestCase):
    """Test the InterruptFilter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.filter = InterruptFilter()
    
    # ==========================================================================
    # Scenario 1: The Long Explanation
    # Agent is speaking, user says filler words -> IGNORE
    # ==========================================================================
    
    def test_scenario1_yeah_while_speaking(self):
        """Agent speaking + 'yeah' -> IGNORE"""
        analysis = self.filter.analyze("yeah", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
        self.assertIn("yeah", analysis.matched_ignore_words)
    
    def test_scenario1_ok_while_speaking(self):
        """Agent speaking + 'ok' -> IGNORE"""
        analysis = self.filter.analyze("ok", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    def test_scenario1_hmm_while_speaking(self):
        """Agent speaking + 'hmm' -> IGNORE"""
        analysis = self.filter.analyze("hmm", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    def test_scenario1_uh_huh_while_speaking(self):
        """Agent speaking + 'uh-huh' -> IGNORE"""
        analysis = self.filter.analyze("uh-huh", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    def test_scenario1_multiple_fillers_while_speaking(self):
        """Agent speaking + 'okay yeah uh-huh' -> IGNORE"""
        analysis = self.filter.analyze("okay yeah uh-huh", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    def test_scenario1_right_while_speaking(self):
        """Agent speaking + 'right' -> IGNORE"""
        analysis = self.filter.analyze("right", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    # ==========================================================================
    # Scenario 2: The Passive Affirmation  
    # Agent is silent, user says anything -> RESPOND
    # ==========================================================================
    
    def test_scenario2_yeah_while_silent(self):
        """Agent silent + 'yeah' -> RESPOND"""
        analysis = self.filter.analyze("yeah", agent_speaking=False)
        self.assertEqual(analysis.decision, "respond")
    
    def test_scenario2_ok_while_silent(self):
        """Agent silent + 'ok' -> RESPOND"""
        analysis = self.filter.analyze("ok", agent_speaking=False)
        self.assertEqual(analysis.decision, "respond")
    
    def test_scenario2_normal_question_while_silent(self):
        """Agent silent + question -> RESPOND"""
        analysis = self.filter.analyze("what's the weather like?", agent_speaking=False)
        self.assertEqual(analysis.decision, "respond")
    
    # ==========================================================================
    # Scenario 3: The Correction
    # Agent is speaking, user says command word -> INTERRUPT
    # ==========================================================================
    
    def test_scenario3_stop_while_speaking(self):
        """Agent speaking + 'stop' -> INTERRUPT"""
        analysis = self.filter.analyze("stop", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
        self.assertIn("stop", analysis.matched_interrupt_words)
    
    def test_scenario3_no_stop_while_speaking(self):
        """Agent speaking + 'no stop' -> INTERRUPT"""
        analysis = self.filter.analyze("no stop", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
    
    def test_scenario3_wait_while_speaking(self):
        """Agent speaking + 'wait' -> INTERRUPT"""
        analysis = self.filter.analyze("wait", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
    
    def test_scenario3_hold_on_while_speaking(self):
        """Agent speaking + 'hold' -> INTERRUPT"""
        analysis = self.filter.analyze("hold on", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
    
    def test_scenario3_pause_while_speaking(self):
        """Agent speaking + 'pause' -> INTERRUPT"""
        analysis = self.filter.analyze("pause", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
    
    # ==========================================================================
    # Scenario 4: The Mixed Input
    # Agent is speaking, user says filler + command -> INTERRUPT
    # ==========================================================================
    
    def test_scenario4_yeah_but_wait(self):
        """Agent speaking + 'yeah but wait' -> INTERRUPT (contains 'wait')"""
        analysis = self.filter.analyze("yeah but wait", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
        self.assertIn("wait", analysis.matched_interrupt_words)
    
    def test_scenario4_ok_but_stop(self):
        """Agent speaking + 'ok but stop' -> INTERRUPT"""
        analysis = self.filter.analyze("ok but stop", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
    
    def test_scenario4_yeah_okay_but_wait_a_second(self):
        """Agent speaking + 'yeah okay but wait a second' -> INTERRUPT"""
        analysis = self.filter.analyze("yeah okay but wait a second", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
    
    def test_scenario4_hmm_actually(self):
        """Agent speaking + 'hmm actually' -> INTERRUPT (contains 'actually')"""
        analysis = self.filter.analyze("hmm actually", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
    
    # ==========================================================================
    # Edge Cases
    # ==========================================================================
    
    def test_edge_empty_string(self):
        """Empty string should not crash"""
        analysis = self.filter.analyze("", agent_speaking=True)
        # Empty string has no content, so it's "only filler" (vacuously true)
        self.assertEqual(analysis.decision, "ignore")
    
    def test_edge_whitespace_only(self):
        """Whitespace only should be ignored"""
        analysis = self.filter.analyze("   ", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    def test_edge_punctuation_only(self):
        """Punctuation handling"""
        analysis = self.filter.analyze("yeah!", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    def test_edge_case_insensitive_yeah(self):
        """Case insensitive matching - YEAH"""
        analysis = self.filter.analyze("YEAH", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    def test_edge_case_insensitive_stop(self):
        """Case insensitive matching - STOP"""
        analysis = self.filter.analyze("STOP", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")
    
    def test_edge_mixed_case(self):
        """Mixed case handling"""
        analysis = self.filter.analyze("YeAh OkAy", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
    
    # ==========================================================================
    # Helper Method Tests
    # ==========================================================================
    
    def test_should_interrupt_false_for_filler(self):
        """should_interrupt returns False for filler while speaking"""
        result = self.filter.should_interrupt("yeah", agent_speaking=True)
        self.assertFalse(result)
    
    def test_should_interrupt_true_for_command(self):
        """should_interrupt returns True for command while speaking"""
        result = self.filter.should_interrupt("stop", agent_speaking=True)
        self.assertTrue(result)
    
    def test_should_interrupt_true_when_silent(self):
        """should_interrupt returns True for any input when silent"""
        result = self.filter.should_interrupt("yeah", agent_speaking=False)
        self.assertTrue(result)
    
    def test_should_ignore_true_for_filler(self):
        """should_ignore returns True for filler while speaking"""
        result = self.filter.should_ignore("yeah", agent_speaking=True)
        self.assertTrue(result)
    
    def test_should_ignore_false_for_command(self):
        """should_ignore returns False for command while speaking"""
        result = self.filter.should_ignore("stop", agent_speaking=True)
        self.assertFalse(result)
    
    def test_should_ignore_false_when_silent(self):
        """should_ignore returns False when agent is silent"""
        result = self.filter.should_ignore("yeah", agent_speaking=False)
        self.assertFalse(result)


class TestCustomConfig(unittest.TestCase):
    """Test custom configuration."""
    
    def test_custom_ignore_words(self):
        """Custom ignore words list"""
        config = InterruptFilterConfig(
            ignore_words=frozenset(["yo", "sup", "cool"]),
            interrupt_words=frozenset(["halt"])
        )
        filter = InterruptFilter(config)
        
        # "yo" should be ignored
        analysis = filter.analyze("yo", agent_speaking=True)
        self.assertEqual(analysis.decision, "ignore")
        
        # "yeah" should NOT be ignored (not in custom list)
        analysis = filter.analyze("yeah", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")  # treated as content
    
    def test_custom_interrupt_words(self):
        """Custom interrupt words list"""
        config = InterruptFilterConfig(
            ignore_words=frozenset(["yeah"]),
            interrupt_words=frozenset(["banana"])  # custom interrupt word
        )
        filter = InterruptFilter(config)
        
        analysis = filter.analyze("banana", agent_speaking=True)
        self.assertEqual(analysis.decision, "interrupt")


class TestLogicMatrix(unittest.TestCase):
    """
    Test the exact logic matrix from the assignment:
    
    | User Input        | Agent State    | Desired Behavior |
    |-------------------|----------------|------------------|
    | Yeah/Ok/Hmm       | Speaking       | IGNORE           |
    | Wait/Stop/No      | Speaking       | INTERRUPT        |
    | Yeah/Ok/Hmm       | Silent         | RESPOND          |
    | Start/Hello       | Silent         | RESPOND          |
    """
    
    def setUp(self):
        self.filter = InterruptFilter()
    
    def test_matrix_row1_filler_while_speaking(self):
        """Row 1: Yeah/Ok/Hmm + Speaking = IGNORE"""
        for word in ["yeah", "ok", "hmm"]:
            analysis = self.filter.analyze(word, agent_speaking=True)
            self.assertEqual(
                analysis.decision, "ignore",
                f"'{word}' while speaking should be IGNORE, got {analysis.decision}"
            )
    
    def test_matrix_row2_command_while_speaking(self):
        """Row 2: Wait/Stop/No + Speaking = INTERRUPT"""
        for word in ["wait", "stop", "no"]:
            analysis = self.filter.analyze(word, agent_speaking=True)
            self.assertEqual(
                analysis.decision, "interrupt",
                f"'{word}' while speaking should be INTERRUPT, got {analysis.decision}"
            )
    
    def test_matrix_row3_filler_while_silent(self):
        """Row 3: Yeah/Ok/Hmm + Silent = RESPOND"""
        for word in ["yeah", "ok", "hmm"]:
            analysis = self.filter.analyze(word, agent_speaking=False)
            self.assertEqual(
                analysis.decision, "respond",
                f"'{word}' while silent should be RESPOND, got {analysis.decision}"
            )
    
    def test_matrix_row4_normal_while_silent(self):
        """Row 4: Start/Hello + Silent = RESPOND"""
        for word in ["start", "hello"]:
            analysis = self.filter.analyze(word, agent_speaking=False)
            self.assertEqual(
                analysis.decision, "respond",
                f"'{word}' while silent should be RESPOND, got {analysis.decision}"
            )


if __name__ == "__main__":
    print("=" * 70)
    print("Running Intelligent Interrupt Filter Tests")
    print("=" * 70)
    
    # Run all tests
    unittest.main(verbosity=2)
