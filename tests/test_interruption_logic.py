import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Ensure livekit-agents is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from livekit.agents.voice.agent_activity import AgentActivity
from livekit.agents.voice.agent_session import AgentSession, AgentSessionOptions
from livekit.agents.voice.agent import Agent
from livekit.agents.voice.speech_handle import SpeechHandle
from livekit.agents.voice.audio_recognition import _EndOfTurnInfo

class TestInterruptionLogic(unittest.TestCase):
    def setUp(self):
        self.agent = MagicMock(spec=Agent)
        self.agent.stt = MagicMock() # Enable STT on agent
        
        self.session = MagicMock(spec=AgentSession)
        self.session.options = AgentSessionOptions(
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
            use_tts_aligned_transcript=False,
            preemptive_generation=False,
            ivr_detection=False,
            ignored_interruption_words=["yeah", "ok", "hmm", "right", "uh-huh"],
            tts_text_transforms=None
        )
        # Mock session.stt as well just in case
        self.session.stt = MagicMock()
        self.session._closing = False
        
        self.activity = AgentActivity(self.agent, self.session)
        self.activity._scheduling_paused = False # IMPORTANT: Unpause scheduling
        # Force set _stt if it wasn't set by init (depending on implementation details)
        # But based on code, it should be fine if agent.stt is set.
        
        self.activity._audio_recognition = MagicMock()

    def test_is_ignored_transcript(self):
        self.assertTrue(self.activity._is_ignored_transcript("yeah"))
        self.assertTrue(self.activity._is_ignored_transcript("Yeah"))
        self.assertTrue(self.activity._is_ignored_transcript("ok..."))
        self.assertTrue(self.activity._is_ignored_transcript("uh-huh"))
        self.assertFalse(self.activity._is_ignored_transcript("stop"))
        self.assertFalse(self.activity._is_ignored_transcript("yeah but"))

    def test_interrupt_by_audio_activity_speaking_vad_only(self):
        # Context: Agent is speaking
        speech = MagicMock(spec=SpeechHandle)
        speech.interrupted = False
        speech.allow_interruptions = True
        self.activity._current_speech = speech
        
        # VAD triggers (no transcript yet)
        self.activity._audio_recognition.current_transcript = ""
        
        # Action
        self.activity._interrupt_by_audio_activity()
        
        # Result: Should NOT interrupt
        speech.interrupt.assert_not_called()

    def test_interrupt_by_audio_activity_speaking_ignored_word(self):
        # Context: Agent is speaking
        speech = MagicMock(spec=SpeechHandle)
        speech.interrupted = False
        speech.allow_interruptions = True
        self.activity._current_speech = speech
        
        # STT triggers "yeah"
        self.activity._audio_recognition.current_transcript = "yeah"
        
        # Action
        self.activity._interrupt_by_audio_activity()
        
        # Result: Should NOT interrupt
        speech.interrupt.assert_not_called()

    def test_interrupt_by_audio_activity_speaking_valid_word(self):
        # Context: Agent is speaking
        speech = MagicMock(spec=SpeechHandle)
        speech.interrupted = False
        speech.allow_interruptions = True
        self.activity._current_speech = speech
        
        # Disable resume_false_interruption to force interrupt()
        self.session.options.resume_false_interruption = False
        
        # STT triggers "stop"
        self.activity._audio_recognition.current_transcript = "stop"
        
        # Action
        self.activity._interrupt_by_audio_activity()
        
        # Result: Should interrupt
        speech.interrupt.assert_called()

    def test_on_end_of_turn_speaking_ignored_word(self):
        # Context: Agent is speaking
        speech = MagicMock(spec=SpeechHandle)
        speech.interrupted = False
        speech.allow_interruptions = True
        self.activity._current_speech = speech
        
        info = _EndOfTurnInfo(
            new_transcript="yeah",
            transcript_confidence=1.0,
            started_speaking_at=0,
            stopped_speaking_at=1,
            transcription_delay=0,
            end_of_turn_delay=0
        )
        
        # Action
        result = self.activity.on_end_of_turn(info)
        
        # Result: Should return False (ignore turn)
        self.assertFalse(result)

    def test_on_end_of_turn_silent_ignored_word(self):
        # Context: Agent is silent
        self.activity._current_speech = None
        
        info = _EndOfTurnInfo(
            new_transcript="yeah",
            transcript_confidence=1.0,
            started_speaking_at=0,
            stopped_speaking_at=1,
            transcription_delay=0,
            end_of_turn_delay=0
        )
        
        # Mock _create_speech_task to avoid actual task creation
        self.activity._create_speech_task = MagicMock()
        
        # Action
        result = self.activity.on_end_of_turn(info)
        
        # Result: Should return True (process turn)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
