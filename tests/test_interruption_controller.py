"""Additional unit tests for InterruptionController state management."""

import pytest
from unittest.mock import Mock, MagicMock

from livekit.agents.voice.interruption import (
    InterruptionConfig,
    InterruptionController,
)


class TestInterruptionController:
    """Test the InterruptionController state management."""

    def test_should_pass_through_when_agent_not_speaking(self):
        """When agent is NOT speaking, all transcripts should pass through."""
        # Mock session with agent in "listening" state
        mock_session = Mock()
        mock_session.agent_state = "listening"
        mock_activity = Mock()
        
        config = InterruptionConfig()
        controller = InterruptionController(config, mock_session, mock_activity)
        
        # All inputs should pass through when agent not speaking
        assert controller.should_process_transcript("yeah", is_final=True) == True
        assert controller.should_process_transcript("stop", is_final=True) == True
        assert controller.should_process_transcript("what time is it", is_final=True) == True

    def test_should_swallow_backchannel_when_agent_speaking(self):
        """When agent IS speaking, backchannel should be swallowed."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        mock_activity = Mock()
        
        config = InterruptionConfig()
        controller = InterruptionController(config, mock_session, mock_activity)
        
        # Backchannel should be swallowed
        assert controller.should_process_transcript("yeah", is_final=True) == False
        assert controller.should_process_transcript("ok hmm", is_final=True) == False
        assert controller.should_process_transcript("right", is_final=True) == False

    def test_should_interrupt_on_command_when_agent_speaking(self):
        """When agent IS speaking, commands should trigger interruption."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        
        # Mock current speech
        mock_speech = Mock()
        mock_activity = Mock()
        mock_activity._current_speech = mock_speech
        
        config = InterruptionConfig()
        controller = InterruptionController(config, mock_session, mock_activity)
        
        # Command should pass through AND trigger interruption
        result = controller.should_process_transcript("stop", is_final=True)
        
        assert result == True  # Passes through
        assert mock_speech.interrupt.called  # Interruption triggered

    def test_should_interrupt_once_per_utterance(self):
        """Interruption should only fire once per utterance."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        
        mock_speech = Mock()
        mock_activity = Mock()
        mock_activity._current_speech = mock_speech
        
        config = InterruptionConfig()
        controller = InterruptionController(config, mock_session, mock_activity)
        
        # First command in utterance
        controller.should_process_transcript("stop", is_final=False)
        assert mock_speech.interrupt.call_count == 1
        
        # Second command in same utterance (before reset)
        controller.should_process_transcript("wait", is_final=False)
        assert mock_speech.interrupt.call_count == 1  # Still 1, not 2

    def test_reset_utterance_clears_state(self):
        """reset_utterance should clear buffer and interruption flag."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        
        mock_speech = Mock()
        mock_activity = Mock()
        mock_activity._current_speech = mock_speech
        
        config = InterruptionConfig()
        controller = InterruptionController(config, mock_session, mock_activity)
        
        # Fire interruption
        controller.should_process_transcript("stop", is_final=False)
        assert controller._interruption_fired == True
        
        # Reset
        controller.reset_utterance()
        assert controller._interruption_fired == False
        assert controller._current_utterance_buffer == ""

    def test_normal_content_with_policy_true(self):
        """With interrupt_on_normal_content=True, normal content should interrupt."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        
        mock_speech = Mock()
        mock_activity = Mock()
        mock_activity._current_speech = mock_speech
        
        config = InterruptionConfig(interrupt_on_normal_content=True)
        controller = InterruptionController(config, mock_session, mock_activity)
        
        result = controller.should_process_transcript("What time is it?", is_final=True)
        
        assert result == True  # Passes through
        assert mock_speech.interrupt.called  # Interruption triggered

    def test_normal_content_with_policy_false(self):
        """With interrupt_on_normal_content=False, normal content should be ignored."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        
        mock_activity = Mock()
        
        config = InterruptionConfig(interrupt_on_normal_content=False)
        controller = InterruptionController(config, mock_session, mock_activity)
        
        result = controller.should_process_transcript("What time is it?", is_final=True)
        
        assert result == False  # Swallowed (rare use case)

    def test_mixed_backchannel_and_command(self):
        """Mixed utterance with command should interrupt."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        
        mock_speech = Mock()
        mock_activity = Mock()
        mock_activity._current_speech = mock_speech
        
        config = InterruptionConfig()
        controller = InterruptionController(config, mock_session, mock_activity)
        
        result = controller.should_process_transcript("yeah okay but wait", is_final=True)
        
        assert result == True  # Passes through
        assert mock_speech.interrupt.called  # Command detected, interrupts

    def test_no_current_speech_safety(self):
        """Command with no current_speech should not crash."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        
        # NO current speech (edge case)
        mock_activity = Mock()
        mock_activity._current_speech = None
        
        config = InterruptionConfig()
        controller = InterruptionController(config, mock_session, mock_activity)
        
        # Should return True and not crash even though there's no speech to interrupt
        result = controller.should_process_transcript("stop", is_final=True)
        
        assert result == True  # Passes through
        # No crash - test passes if we get here

    def test_empty_text_when_agent_speaking(self):
        """Empty/noise text while agent speaking should be swallowed."""
        mock_session = Mock()
        mock_session.agent_state = "speaking"
        mock_activity = Mock()
        
        config = InterruptionConfig()
        controller = InterruptionController(config, mock_session, mock_activity)
        
        # Empty and whitespace should be classified as BACKCHANNEL and swallowed
        assert controller.should_process_transcript("", is_final=True) == False
        assert controller.should_process_transcript("   ", is_final=True) == False
        assert controller.should_process_transcript("\n\t", is_final=True) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
