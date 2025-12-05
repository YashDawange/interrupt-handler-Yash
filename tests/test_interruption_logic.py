import pytest
from unittest.mock import Mock, MagicMock
from livekit.agents.voice.agent_activity import AgentActivity
from livekit.agents.voice.agent_session import AgentSession, AgentSessionOptions
from livekit.agents.voice.audio_recognition import _EndOfTurnInfo
from livekit.agents.voice.agent import Agent


class TestInterruptionLogic:
    @pytest.fixture
    def session_mock(self):
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
    def agent_mock(self):
        agent = Mock(spec=Agent)
        agent.turn_detection = None
        agent.allow_interruptions = True
        return agent

    @pytest.fixture
    def activity_instance(self, agent_mock, session_mock):
        agent_mock.vad = None
        agent_mock.stt = None
        agent_mock.llm = None
        agent_mock.tts = None
        
        activity = AgentActivity(agent_mock, session_mock)
        return activity

    def test_single_word_ignored(self, activity_instance):
        assert activity_instance._is_ignored_transcript("yeah") is True
        assert activity_instance._is_ignored_transcript("ok") is True
        assert activity_instance._is_ignored_transcript("hmm") is True
        assert activity_instance._is_ignored_transcript("right") is True
        assert activity_instance._is_ignored_transcript("uh-huh") is True

    def test_punctuation_stripping(self, activity_instance):
        assert activity_instance._is_ignored_transcript("yeah!") is True
        assert activity_instance._is_ignored_transcript("ok.") is True
        assert activity_instance._is_ignored_transcript("hmm?") is True
        assert activity_instance._is_ignored_transcript("right...") is True

    def test_case_insensitivity(self, activity_instance):
        assert activity_instance._is_ignored_transcript("YEAH") is True
        assert activity_instance._is_ignored_transcript("Ok") is True
        assert activity_instance._is_ignored_transcript("HMM") is True

    def test_multiple_ignored_words(self, activity_instance):
        assert activity_instance._is_ignored_transcript("yeah ok") is True
        assert activity_instance._is_ignored_transcript("hmm right") is True
        assert activity_instance._is_ignored_transcript("yeah ok hmm") is True

    def test_mixed_valid_invalid_words(self, activity_instance):
        assert activity_instance._is_ignored_transcript("yeah but wait") is False
        assert activity_instance._is_ignored_transcript("ok stop") is False
        assert activity_instance._is_ignored_transcript("hmm hello") is False
        assert activity_instance._is_ignored_transcript("wait a second") is False

    def test_non_ignored_words(self, activity_instance):
        assert activity_instance._is_ignored_transcript("stop") is False
        assert activity_instance._is_ignored_transcript("wait") is False
        assert activity_instance._is_ignored_transcript("hello") is False
        assert activity_instance._is_ignored_transcript("help me") is False

    def test_empty_string(self, activity_instance):
        assert activity_instance._is_ignored_transcript("") is False
        assert activity_instance._is_ignored_transcript("   ") is False

    def test_no_interrupt_when_speaking_ignored_word(self, activity_instance, mocker):
        mock_speech = Mock()
        mock_speech.interrupted = False
        mock_speech.allow_interruptions = True
        activity_instance._current_speech = mock_speech

        activity_instance._agent.stt = Mock()
        activity_instance._audio_recognition = Mock()
        activity_instance._audio_recognition.current_transcript = "yeah"

        activity_instance._interrupt_by_audio_activity()

        assert activity_instance._current_speech == mock_speech
        assert activity_instance._paused_speech is None

    def test_interrupt_when_speaking_valid_word(self, activity_instance, mocker):
        mock_speech = Mock()
        mock_speech.interrupted = False
        mock_speech.allow_interruptions = True
        mock_speech.interrupt = Mock()
        activity_instance._current_speech = mock_speech

        activity_instance._agent.stt = Mock()
        activity_instance._audio_recognition = Mock()
        activity_instance._audio_recognition.current_transcript = "stop"
        activity_instance._session.output = Mock()
        activity_instance._session.output.audio = Mock()
        activity_instance._session.output.audio.can_pause = False

        activity_instance._interrupt_by_audio_activity()

        assert activity_instance._paused_speech == mock_speech
        mock_speech.interrupt.assert_called_once()

    def test_no_interrupt_vad_only(self, activity_instance):
        mock_speech = Mock()
        mock_speech.interrupted = False
        mock_speech.allow_interruptions = True
        activity_instance._current_speech = mock_speech

        activity_instance._agent.stt = Mock()
        activity_instance._audio_recognition = Mock()
        activity_instance._audio_recognition.current_transcript = ""

        activity_instance._interrupt_by_audio_activity()

        assert activity_instance._paused_speech is None

    def test_eou_speaking_ignored_word(self, activity_instance, mocker):
        mock_speech = Mock()
        mock_speech.allow_interruptions = True
        mock_speech.interrupted = False
        mock_speech.done = Mock(return_value=False)
        activity_instance._current_speech = mock_speech
        activity_instance._scheduling_paused = False

        activity_instance._cancel_preemptive_generation = Mock()

        info = Mock(spec=_EndOfTurnInfo)
        info.new_transcript = "yeah"

        result = activity_instance.on_end_of_turn(info)

        assert result is False
        activity_instance._cancel_preemptive_generation.assert_called_once()

    def test_eou_silent_ignored_word(self, activity_instance, mocker):
        activity_instance._current_speech = None
        activity_instance._scheduling_paused = False
        activity_instance._user_turn_completed_atask = None

        mock_task = Mock()
        activity_instance._create_speech_task = Mock(return_value=mock_task)

        info = Mock(spec=_EndOfTurnInfo)
        info.new_transcript = "yeah"

        result = activity_instance.on_end_of_turn(info)

        assert result is True
        activity_instance._create_speech_task.assert_called_once()

    def test_eou_speaking_valid_interruption(self, activity_instance, mocker):
        mock_speech = Mock()
        mock_speech.allow_interruptions = True
        mock_speech.interrupted = False
        mock_speech.done = Mock(return_value=False)
        activity_instance._current_speech = mock_speech
        activity_instance._scheduling_paused = False
        activity_instance._user_turn_completed_atask = None

        mock_task = Mock()
        activity_instance._create_speech_task = Mock(return_value=mock_task)

        info = Mock(spec=_EndOfTurnInfo)
        info.new_transcript = "stop"

        result = activity_instance.on_end_of_turn(info)

        assert result is True
        activity_instance._create_speech_task.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])