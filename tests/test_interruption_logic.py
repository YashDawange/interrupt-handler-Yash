"""
Unit tests for intelligent interruption handling in LiveKit Agents.
Tests the _is_ignored_transcript method and interruption logic.
"""
import pytest
from unittest.mock import Mock, MagicMock
from livekit.agents.voice.agent_activity import AgentActivity
from livekit.agents.voice.agent_session import AgentSession, AgentSessionOptions
from livekit.agents.voice.audio_recognition import _EndOfTurnInfo
from livekit.agents.voice.agent import Agent


class TestInterruptionLogic:
    """Test suite for intelligent interruption handling."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AgentSession with test options."""
        session = Mock(spec=AgentSession)
        session.options = AgentSessionOptions(
            allow_interruptions=True,
            discard_audio_if_uninterruptible=True,
            min_interruption_duration=0.5,
            min_interruption_words=0,
            min_endpointing_delay=0.5,
            max_endpointing_delay=3.0,
            max_tool_steps=3,
            user_away_timeout=15.0,
            false_interruption_timeout=2.0,
            resume_false_interruption=True,
            min_consecutive_speech_delay=0.0,
            use_tts_aligned_transcript=None,
            preemptive_generation=False,
            tts_text_transforms=None,
            ivr_detection=False,
            ignore_words=[],
            ignored_interruption_words=["yeah", "ok", "hmm", "right", "uh-huh"],
        )
        return session

    @pytest.fixture
    def mock_agent(self):
        """Create a mock Agent."""
        agent = Mock(spec=Agent)
        agent.turn_detection = None
        agent.allow_interruptions = True
        return agent

    @pytest.fixture
    def agent_activity(self, mock_agent, mock_session):
        """Create an AgentActivity instance for testing."""
        # Mock the necessary attributes to prevent initialization issues
        mock_agent.vad = None
        mock_agent.stt = None
        mock_agent.llm = None
        mock_agent.tts = None
        
        activity = AgentActivity(mock_agent, mock_session)
        return activity

    def test_is_ignored_transcript_single_word(self, agent_activity):
        """Test that single ignored words are correctly identified."""
        assert agent_activity._is_ignored_transcript("yeah") is True
        assert agent_activity._is_ignored_transcript("ok") is True
        assert agent_activity._is_ignored_transcript("hmm") is True
        assert agent_activity._is_ignored_transcript("right") is True
        assert agent_activity._is_ignored_transcript("uh-huh") is True

    def test_is_ignored_transcript_with_punctuation(self, agent_activity):
        """Test that punctuation is correctly stripped."""
        assert agent_activity._is_ignored_transcript("yeah!") is True
        assert agent_activity._is_ignored_transcript("ok.") is True
        assert agent_activity._is_ignored_transcript("hmm?") is True
        assert agent_activity._is_ignored_transcript("right...") is True

    def test_is_ignored_transcript_case_insensitive(self, agent_activity):
        """Test that matching is case-insensitive."""
        assert agent_activity._is_ignored_transcript("YEAH") is True
        assert agent_activity._is_ignored_transcript("Ok") is True
        assert agent_activity._is_ignored_transcript("HMM") is True

    def test_is_ignored_transcript_multiple_ignored_words(self, agent_activity):
        """Test that multiple ignored words together are still ignored."""
        assert agent_activity._is_ignored_transcript("yeah ok") is True
        assert agent_activity._is_ignored_transcript("hmm right") is True
        assert agent_activity._is_ignored_transcript("yeah ok hmm") is True

    def test_is_ignored_transcript_mixed_with_valid_word(self, agent_activity):
        """Test that mixed input with valid words is NOT ignored."""
        assert agent_activity._is_ignored_transcript("yeah but wait") is False
        assert agent_activity._is_ignored_transcript("ok stop") is False
        assert agent_activity._is_ignored_transcript("hmm hello") is False
        assert agent_activity._is_ignored_transcript("wait a second") is False

    def test_is_ignored_transcript_non_ignored_words(self, agent_activity):
        """Test that non-ignored words return False."""
        assert agent_activity._is_ignored_transcript("stop") is False
        assert agent_activity._is_ignored_transcript("wait") is False
        assert agent_activity._is_ignored_transcript("hello") is False
        assert agent_activity._is_ignored_transcript("help me") is False

    def test_is_ignored_transcript_empty_string(self, agent_activity):
        """Test that empty strings return False."""
        assert agent_activity._is_ignored_transcript("") is False
        assert agent_activity._is_ignored_transcript("   ") is False

    def test_interrupt_by_audio_activity_speaking_ignored_word(self, agent_activity, mocker):
        """Test that agent does NOT interrupt when speaking and user says ignored word."""
        # Setup: Agent is speaking
        mock_speech = Mock()
        mock_speech.interrupted = False
        mock_speech.allow_interruptions = True
        agent_activity._current_speech = mock_speech

        # Setup: STT and audio recognition available with ignored word
        agent_activity._agent.stt = Mock()
        agent_activity._audio_recognition = Mock()
        agent_activity._audio_recognition.current_transcript = "yeah"

        # Call the method
        agent_activity._interrupt_by_audio_activity()

        # Assert: Speech should NOT be interrupted
        assert agent_activity._current_speech == mock_speech
        assert agent_activity._paused_speech is None

    def test_interrupt_by_audio_activity_speaking_valid_word(self, agent_activity, mocker):
        """Test that agent DOES interrupt when speaking and user says non-ignored word."""
        # Setup: Agent is speaking
        mock_speech = Mock()
        mock_speech.interrupted = False
        mock_speech.allow_interruptions = True
        mock_speech.interrupt = Mock()
        agent_activity._current_speech = mock_speech

        # Setup: STT and audio recognition available with valid interruption
        agent_activity._agent.stt = Mock()
        agent_activity._audio_recognition = Mock()
        agent_activity._audio_recognition.current_transcript = "stop"
        agent_activity._session.output = Mock()
        agent_activity._session.output.audio = Mock()
        agent_activity._session.output.audio.can_pause = False

        # Call the method
        agent_activity._interrupt_by_audio_activity()

        # Assert: Speech should be paused/interrupted
        assert agent_activity._paused_speech == mock_speech
        mock_speech.interrupt.assert_called_once()

    def test_interrupt_by_audio_activity_speaking_vad_only(self, agent_activity):
        """Test that VAD-only (no transcript yet) does NOT interrupt."""
        # Setup: Agent is speaking
        mock_speech = Mock()
        mock_speech.interrupted = False
        mock_speech.allow_interruptions = True
        agent_activity._current_speech = mock_speech

        # Setup: STT available but NO transcript yet (VAD only)
        agent_activity._agent.stt = Mock()
        agent_activity._audio_recognition = Mock()
        agent_activity._audio_recognition.current_transcript = ""  # Empty = no transcript yet

        # Call the method
        agent_activity._interrupt_by_audio_activity()

        # Assert: Should NOT interrupt (waiting for STT)
        assert agent_activity._paused_speech is None

    def test_on_end_of_turn_speaking_ignored_word(self, agent_activity, mocker):
        """Test on_end_of_turn ignores turn when agent is speaking and user says ignored word."""
        # Setup: Agent is speaking
        mock_speech = Mock()
        mock_speech.allow_interruptions = True
        mock_speech.interrupted = False
        mock_speech.done = Mock(return_value=False)
        agent_activity._current_speech = mock_speech
        agent_activity._scheduling_paused = False

        # Mock _cancel_preemptive_generation
        agent_activity._cancel_preemptive_generation = Mock()

        # Setup end of turn info with ignored word
        info = Mock(spec=_EndOfTurnInfo)
        info.new_transcript = "yeah"

        # Call the method
        result = agent_activity.on_end_of_turn(info)

        # Assert: Should return False (turn ignored)
        assert result is False
        agent_activity._cancel_preemptive_generation.assert_called_once()

    def test_on_end_of_turn_silent_ignored_word(self, agent_activity, mocker):
        """Test on_end_of_turn processes turn when agent is silent, even with ignored word."""
        # Setup: Agent is NOT speaking (idle)
        agent_activity._current_speech = None
        agent_activity._scheduling_paused = False
        agent_activity._user_turn_completed_atask = None

        # Mock _create_speech_task
        mock_task = Mock()
        agent_activity._create_speech_task = Mock(return_value=mock_task)

        # Setup end of turn info with ignored word
        info = Mock(spec=_EndOfTurnInfo)
        info.new_transcript = "yeah"

        # Call the method
        result = agent_activity.on_end_of_turn(info)

        # Assert: Should return True (turn processed)
        assert result is True
        agent_activity._create_speech_task.assert_called_once()

    def test_on_end_of_turn_speaking_valid_interruption(self, agent_activity, mocker):
        """Test on_end_of_turn processes turn when user says valid interruption."""
        # Setup: Agent is speaking
        mock_speech = Mock()
        mock_speech.allow_interruptions = True
        mock_speech.interrupted = False
        mock_speech.done = Mock(return_value=False)
        agent_activity._current_speech = mock_speech
        agent_activity._scheduling_paused = False
        agent_activity._user_turn_completed_atask = None

        # Mock _create_speech_task
        mock_task = Mock()
        agent_activity._create_speech_task = Mock(return_value=mock_task)

        # Setup end of turn info with valid interruption
        info = Mock(spec=_EndOfTurnInfo)
        info.new_transcript = "stop"

        # Call the method
        result = agent_activity.on_end_of_turn(info)

        # Assert: Should return True (turn processed)
        assert result is True
        agent_activity._create_speech_task.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
