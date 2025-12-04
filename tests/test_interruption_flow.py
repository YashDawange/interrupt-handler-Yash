import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import asyncio
import logging

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../livekit-agents')))

# Mock dependencies before importing agent_activity
# We need to mock livekit.agents.voice.agent_activity.logger to capture logs
with patch('livekit.agents.voice.agent_activity.logger') as mock_logger:
    from livekit.agents.voice.agent_activity import AgentActivity, _EndOfTurnInfo

class TestInterruptionFlow(unittest.TestCase):
    def setUp(self):
        self.mock_agent = MagicMock()
        self.mock_session = MagicMock()
        
        # Mock __init__ to avoid complex setup
        original_init = AgentActivity.__init__
        AgentActivity.__init__ = lambda self, agent, sess: None
        self.activity = AgentActivity(self.mock_agent, self.mock_session)
        # Restore __init__ 
        # AgentActivity.__init__ = original_init
        
        # Manually set attributes needed for the test
        self.activity._agent = self.mock_agent
        self.activity._session = self.mock_session
        self.activity._scheduling_paused = False
        self.activity._background_speeches = set()
        self.activity._interrupt_paused_speech_task = None
        self.activity._interrupt_paused_speech = MagicMock()
        self.activity._interrupt_paused_speech.return_value = asyncio.Future()
        self.activity._interrupt_paused_speech.return_value.set_result(None)
        self.activity._rt_session = None
        self.mock_agent.llm = MagicMock()
        
        # Mock _is_ignored_transcript (we already tested it, but we can use the real one or mock it)
        # Let's use the real one to be sure
        # We need to re-bind the method if we mocked __init__? No, it's a class method.
        
    def test_ignore_interruption_when_speaking(self):
        # Setup: Agent is speaking
        mock_speech = MagicMock()
        mock_speech.done.return_value = False # Not done speaking
        self.activity._current_speech = mock_speech
        
        # Setup: User says "yeah"
        info = MagicMock(spec=_EndOfTurnInfo)
        info.new_transcript = "yeah"
        
        # Mock logger
        with patch('livekit.agents.voice.agent_activity.logger') as mock_logger:
            # Call on_user_turn_completed
            # We need to run this async method
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # We need to mock _is_ignored_transcript if it wasn't bound correctly, 
            # but it should be fine.
            
            # Execute
            result = loop.run_until_complete(self.activity._user_turn_completed_task(None, info))
            
            # Verify
            # Should return None (implicit) when it returns early.
            
            # Check if logger was called with the expected message
            mock_logger.debug.assert_called_with("ignoring user input 'yeah' while agent is speaking")
            
            # Verify that _agent.on_user_turn_completed was NOT called
            self.activity._agent.on_user_turn_completed.assert_not_called()

    def test_interrupt_when_speaking_hard_input(self):
        # Setup: Agent is speaking
        mock_speech = MagicMock()
        mock_speech.done.return_value = False
        mock_speech.interrupt.return_value = asyncio.Future()
        mock_speech.interrupt.return_value.set_result(None)
        self.activity._current_speech = mock_speech
        
        # Setup: User says "stop"
        info = MagicMock(spec=_EndOfTurnInfo)
        info.new_transcript = "stop"
        info.transcript_confidence = 1.0
        
        # Mock other methods called in on_user_turn_completed
        self.activity._create_speech_task = MagicMock()
        
        # Mock logger
        with patch('livekit.agents.voice.agent_activity.logger') as mock_logger:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Execute
            loop.run_until_complete(self.activity._user_turn_completed_task(None, info))
            
            # Verify
            # Should NOT log "ignoring user input"
            # mock_logger.debug.assert_not_called() # It might be called for other things
            
            # Check that it proceeded to call agent's on_user_turn_completed
            self.activity._agent.on_user_turn_completed.assert_called()

if __name__ == '__main__':
    unittest.main()
