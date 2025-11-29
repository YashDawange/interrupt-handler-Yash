import unittest
from intelligent_interruption_agent import IntelligentInterruptionHandler


class TestInterruptionHandler(unittest.TestCase):
    
    def setUp(self):
        self.handler = IntelligentInterruptionHandler()
    
    def test_ignore_single_passive_word_while_speaking(self):
        """Test that single passive words are ignored when agent is speaking"""
        self.assertTrue(self.handler.should_ignore_input("yeah", True))
        self.assertTrue(self.handler.should_ignore_input("ok", True))
        self.assertTrue(self.handler.should_ignore_input("hmm", True))
        self.assertTrue(self.handler.should_ignore_input("right", True))
        
    def test_not_ignore_single_passive_word_while_silent(self):
        """Test that single passive words are NOT ignored when agent is silent"""
        self.assertFalse(self.handler.should_ignore_input("yeah", False))
        self.assertFalse(self.handler.should_ignore_input("ok", False))
        self.assertFalse(self.handler.should_ignore_input("hmm", False))
        
    def test_not_ignore_interrupt_words_while_speaking(self):
        """Test that interrupt words are NOT ignored even when agent is speaking"""
        self.assertFalse(self.handler.should_ignore_input("stop", True))
        self.assertFalse(self.handler.should_ignore_input("wait", True))
        self.assertFalse(self.handler.should_ignore_input("no", True))
        
    def test_not_ignore_interrupt_words_while_silent(self):
        """Test that interrupt words are NOT ignored when agent is silent"""
        self.assertFalse(self.handler.should_ignore_input("stop", False))
        self.assertFalse(self.handler.should_ignore_input("wait", False))
        self.assertFalse(self.handler.should_ignore_input("no", False))
        
    def test_ignore_multiple_passive_words_while_speaking(self):
        """Test that multiple passive words are ignored when agent is speaking"""
        self.assertTrue(self.handler.should_ignore_input("yeah ok hmm", True))
        self.assertTrue(self.handler.should_ignore_input("right uh-huh got it", True))
        
    def test_not_ignore_mixed_words_with_interrupt_while_speaking(self):
        """Test that mixed words containing interrupt words are NOT ignored"""
        self.assertFalse(self.handler.should_ignore_input("yeah wait", True))
        self.assertFalse(self.handler.should_ignore_input("ok stop", True))
        self.assertFalse(self.handler.should_ignore_input("hmm no", True))
        
    def test_not_ignore_mixed_words_with_interrupt_while_silent(self):
        """Test that mixed words containing interrupt words are NOT ignored when silent"""
        self.assertFalse(self.handler.should_ignore_input("yeah wait", False))
        self.assertFalse(self.handler.should_ignore_input("ok stop", False))
        
    def test_normalization(self):
        """Test that text normalization works correctly"""
        # Test case insensitivity
        self.assertTrue(self.handler.should_ignore_input("YEAH", True))
        self.assertTrue(self.handler.should_ignore_input("Yeah", True))
        self.assertTrue(self.handler.should_ignore_input("yEaH", True))
        
        # Test punctuation removal
        self.assertTrue(self.handler.should_ignore_input("yeah!", True))
        self.assertTrue(self.handler.should_ignore_input("ok?", True))
        self.assertTrue(self.handler.should_ignore_input("hmm...", True))
        
        # Test extra whitespace
        self.assertTrue(self.handler.should_ignore_input("  yeah  ", True))
        self.assertTrue(self.handler.should_ignore_input("ok   ok", True))


if __name__ == '__main__':
    unittest.main()