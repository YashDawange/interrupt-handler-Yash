import unittest
from unittest.mock import MagicMock
import sys
import os

# Add the project root to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../livekit-agents')))

from livekit.agents.voice.agent_activity import AgentActivity

class TestInterruptionLogic(unittest.TestCase):
    def setUp(self):
        # Mock dependencies for AgentActivity
        self.mock_agent = MagicMock()
        self.mock_session = MagicMock()
        
        # We can't easily instantiate AgentActivity because of its complex __init__
        # So we will dynamically add the method to a mock object or subclass it if needed
        # But since we modified the class, we can just use the class method if we can instantiate it
        # Let's try to mock the __init__ to do nothing
        
        original_init = AgentActivity.__init__
        AgentActivity.__init__ = lambda self, agent, sess: None
        
        self.activity = AgentActivity(self.mock_agent, self.mock_session)
        
        # Restore __init__ just in case (though not strictly needed for this script)
        # AgentActivity.__init__ = original_init

    def test_is_ignored_transcript(self):
        # Test ignored words
        self.assertTrue(self.activity._is_ignored_transcript("yeah"))
        self.assertTrue(self.activity._is_ignored_transcript("Yeah"))
        self.assertTrue(self.activity._is_ignored_transcript("ok"))
        self.assertTrue(self.activity._is_ignored_transcript("OK"))
        self.assertTrue(self.activity._is_ignored_transcript("hmm"))
        self.assertTrue(self.activity._is_ignored_transcript("uh-huh"))
        self.assertTrue(self.activity._is_ignored_transcript("right"))
        
        # Test with punctuation
        self.assertTrue(self.activity._is_ignored_transcript("Yeah."))
        self.assertTrue(self.activity._is_ignored_transcript("OK!"))
        self.assertTrue(self.activity._is_ignored_transcript("hmm..."))
        
        # Test NOT ignored words
        self.assertFalse(self.activity._is_ignored_transcript("stop"))
        self.assertFalse(self.activity._is_ignored_transcript("wait"))
        self.assertFalse(self.activity._is_ignored_transcript("no"))
        self.assertFalse(self.activity._is_ignored_transcript("hello"))
        
        # Test mixed sentences (should NOT be ignored)
        self.assertFalse(self.activity._is_ignored_transcript("yeah wait"))
        self.assertFalse(self.activity._is_ignored_transcript("ok stop"))
        self.assertFalse(self.activity._is_ignored_transcript("yeah but"))

if __name__ == '__main__':
    unittest.main()
