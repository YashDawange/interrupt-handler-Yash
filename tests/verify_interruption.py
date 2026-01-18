import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from livekit.agents.voice.agent_activity import AgentActivity
from livekit.agents.voice.agent_session import AgentSession, AgentSessionOptions
from livekit.agents import Agent
from livekit.agents.voice.speech_handle import SpeechHandle
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestInterruptionLogic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_agent = MagicMock(spec=Agent)
        self.mock_session = MagicMock(spec=AgentSession)

        # Mock options
        self.mock_options = MagicMock(spec=AgentSessionOptions)
        self.mock_options.interruption_speech_filter = []
        self.mock_options.min_interruption_words = 0
        self.mock_options.resume_false_interruption = False
        self.mock_options.false_interruption_timeout = None

        self.mock_session.options = self.mock_options

        # Mock AudioRecognition
        self.mock_audio_recognition = MagicMock()
        self.mock_audio_recognition.current_transcript = ""

        # Initialize AgentActivity
        self.activity = AgentActivity(self.mock_agent, self.mock_session)
        self.activity._audio_recognition = self.mock_audio_recognition

        # Mock properties that don't have setters
        type(self.activity).stt = MagicMock()

        # Mock current speech
        self.mock_speech = MagicMock(spec=SpeechHandle)
        self.mock_speech.interrupted = False
        self.mock_speech.done.return_value = False
        self.mock_speech.allow_interruptions = True
        self.activity._current_speech = self.mock_speech

        # Mock RT session
        self.activity._rt_session = MagicMock()

    async def test_no_filter_vad_only(self):
        """Test default behavior: VAD with empty transcript interrupts"""
        logger.info("Test: VAD only, no filter")
        self.mock_options.interruption_speech_filter = []
        self.mock_audio_recognition.current_transcript = ""

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_called()

    async def test_filter_enabled_vad_only(self):
        """Test filter enabled: VAD with empty transcript should NOT interrupt"""
        logger.info("Test: VAD only, filter enabled")
        self.mock_options.interruption_speech_filter = ["yeah", "ok"]
        self.mock_audio_recognition.current_transcript = ""

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_not_called()

    async def test_filter_enabled_ignored_word(self):
        """Test filter enabled: Transcript contains ignored word should NOT interrupt"""
        logger.info("Test: 'Yeah', filter enabled")
        self.mock_options.interruption_speech_filter = ["yeah", "ok"]
        self.mock_audio_recognition.current_transcript = "Yeah"

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_not_called()

    async def test_filter_enabled_multiple_ignored_words(self):
        """Test filter enabled: Transcript contains multiple ignored words should NOT interrupt"""
        logger.info("Test: 'Yeah ok', filter enabled")
        self.mock_options.interruption_speech_filter = ["yeah", "ok"]
        self.mock_audio_recognition.current_transcript = "Yeah ok"

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_not_called()

    async def test_filter_enabled_non_ignored_word(self):
        """Test filter enabled: Transcript contains non-ignored word should interrupt"""
        logger.info("Test: 'Stop', filter enabled")
        self.mock_options.interruption_speech_filter = ["yeah", "ok"]
        self.mock_audio_recognition.current_transcript = "Stop"

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_called()

    async def test_filter_enabled_mixed_input(self):
        """Test filter enabled: Transcript contains mixed ignored and non-ignored words should interrupt"""
        logger.info("Test: 'Yeah wait', filter enabled")
        self.mock_options.interruption_speech_filter = ["yeah", "ok"]
        self.mock_audio_recognition.current_transcript = "Yeah wait"

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_called()

    async def test_punctuation_handling(self):
        """Test filter enabled: Punctuation should be ignored"""
        logger.info("Test: 'Yeah.', filter enabled")
        self.mock_options.interruption_speech_filter = ["yeah"]
        self.mock_audio_recognition.current_transcript = "Yeah."

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_not_called()

    async def test_hyphen_handling(self):
        """Test filter enabled: Hyphens should be preserved"""
        logger.info("Test: 'Uh-huh', filter enabled")
        self.mock_options.interruption_speech_filter = ["uh-huh"]
        self.mock_audio_recognition.current_transcript = "Uh-huh"

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_not_called()

    async def test_silent_agent_handling(self):
        """Test: Agent silent + 'Yeah'. Should NOT trigger interrupt logic (because no speech), but verify logic doesn't crash or block."""
        logger.info("Test: Silent agent + 'Yeah'")
        self.mock_options.interruption_speech_filter = ["yeah"]
        self.mock_audio_recognition.current_transcript = "Yeah"
        self.activity._current_speech = None # Agent silent

        # This method is called to *interrupt* current speech. If no speech, it does nothing or returns early.
        # We just want to ensure it doesn't raise error or do something weird.
        self.activity._interrupt_by_audio_activity()

        # No interrupt called because no speech handle
        pass

    async def test_space_handling(self):
        """Test: 'Uh huh' (space) vs filter 'uh-huh'."""
        logger.info("Test: 'Uh huh' vs filter 'uh-huh'")
        # If the user only puts 'uh-huh' in filter, 'uh huh' (two words) will fail the check if we rely on strict word matching.
        # This test documents the behavior: User must add 'uh' and 'huh' OR we need fuzzy matching.
        # Current logic: strict word match. So this should INTERRUPT.

        self.mock_options.interruption_speech_filter = ["uh-huh"]
        self.mock_audio_recognition.current_transcript = "Uh huh"

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_called()

    async def test_apostrophe_handling(self):
        """Test: 'It's ok' with filter 'it's', 'ok'."""
        logger.info("Test: 'It's ok' with filter")
        self.mock_options.interruption_speech_filter = ["it's", "ok"]
        self.mock_audio_recognition.current_transcript = "It's ok"

        self.activity._interrupt_by_audio_activity()

        self.mock_speech.interrupt.assert_not_called()

    async def test_silent_agent_vad_only(self):
        """Test: Agent silent + VAD only. Should NOT return early (filter ignored), so it should reach start_user_activity."""
        logger.info("Test: Silent agent + VAD only")
        self.mock_options.interruption_speech_filter = ["yeah"]
        self.mock_audio_recognition.current_transcript = ""
        self.activity._current_speech = None # Agent silent

        self.activity._interrupt_by_audio_activity()

        # Verify start_user_activity was called (meaning we didn't return early)
        self.activity._rt_session.start_user_activity.assert_called()

if __name__ == '__main__':
    unittest.main()
