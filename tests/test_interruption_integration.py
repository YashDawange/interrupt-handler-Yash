"""Integration tests for semantic interruption handling.

These tests validate the full pipeline from STT events through the controller
to agent behavior, using the existing FakeActions infrastructure.
"""

import asyncio
import pytest

from livekit.agents import Agent
from livekit.agents.voice.interruption import InterruptionConfig

# Import test infrastructure
from .fake_session import FakeActions, create_session, run_session


class InterruptionTestAgent(Agent):
    """Simple test agent for integration tests."""

    def __init__(self):
        super().__init__(instructions="You are a helpful assistant.")


SESSION_TIMEOUT = 60.0


class TestInterruptionIntegration:
    """Integration tests for semantic interruption handling."""

    @pytest.mark.asyncio
    async def test_backchannel_during_agent_speech_no_interruption(self):
        """User says 'yeah ok' while agent is speaking → No interruption."""
        actions = FakeActions()
        
        # User asks question
        actions.add_user_speech(0.5, 2.0, "Tell me about Paris")
        
        # LLM responds with long answer
        actions.add_llm("Paris is the capital of France and one of the most beautiful cities.")
        
        # TTS starts (long duration)
        actions.add_tts(10.0)
        
        # User says backchannel during TTS (at 5 seconds)
        actions.add_user_speech(5.0, 5.5, "yeah ok")
        
        # Create session with semantic interruption
        session = create_session(
            actions,
            extra_kwargs={
                "discard_audio_if_uninterruptible": False,  # CRITICAL
                "interruption_config": InterruptionConfig(),
            }
        )
        
        # Track interruptions
        interruptions = []
        
        @session.on("agent_speech_interrupted")
        def on_interrupted(ev):
            interruptions.append(ev)
        
        # Run session
        await asyncio.wait_for(run_session(session, InterruptionTestAgent()), timeout=SESSION_TIMEOUT)
        
        # Assert: No interruption occurred (backchannel was swallowed)
        assert len(interruptions) == 0, "Backchannel should not interrupt"

    @pytest.mark.asyncio
    async def test_command_during_agent_speech_interrupts(self):
        """User says 'stop' while agent is speaking → Immediate interruption."""
        actions = FakeActions()
        
        # User asks question
        actions.add_user_speech(0.5, 2.0, "Tell me about Paris")
        
        # LLM responds
        actions.add_llm("Paris is the capital of France...")
        actions.add_tts(10.0)
        
        # User says COMMAND during TTS
        actions.add_user_speech(3.0, 3.5, "stop")
        
        session = create_session(
            actions,
            extra_kwargs={
                "discard_audio_if_uninterruptible": False,
                "interruption_config": InterruptionConfig(),
            }
        )
        
        interruptions = []
        
        @session.on("agent_speech_interrupted")
        def on_interrupted(ev):
            interruptions.append(ev)
        
        await asyncio.wait_for(run_session(session, InterruptionTestAgent()), timeout=SESSION_TIMEOUT)
        
        # Assert: Interruption occurred
        assert len(interruptions) > 0, "Command should interrupt"

    @pytest.mark.asyncio
    async def test_backchannel_when_agent_silent_creates_turn(self):
        """User says 'yeah' when agent is silent → Normal user turn."""
        actions = FakeActions()
        
        # User responds with backchannel when agent is silent
        actions.add_user_speech(1.0, 1.5, "yeah")
        
        # LLM should respond (backchannel is treated as normal input when silent)
        actions.add_llm("Great! How can I help you further?")
        actions.add_tts(3.0)
        
        session = create_session(
            actions,
            extra_kwargs={
                "discard_audio_if_uninterruptible": False,
                "interruption_config": InterruptionConfig(),
            }
        )
        
        llm_calls = []
        
        @session.on("user_turn_completed")
        def on_turn(ev):
            llm_calls.append(ev)
        
        await asyncio.wait_for(run_session(session, InterruptionTestAgent()), timeout=SESSION_TIMEOUT)
        
        # Assert: LLM was called (backchannel was processed as normal turn)
        assert len(llm_calls) > 0, "Backchannel when silent should create turn"

    @pytest.mark.asyncio
    async def test_mixed_utterance_with_command(self):
        """User says 'yeah okay but wait' while agent speaking → Interrupts."""
        actions = FakeActions()
        
        actions.add_user_speech(0.5, 2.0, "Explain quantum physics")
        actions.add_llm("Quantum physics is a fundamental theory...")
        actions.add_tts(15.0)
        
        # Mixed utterance: backchannel + command
        actions.add_user_speech(5.0, 6.0, "yeah okay but wait a second")
        
        session = create_session(
            actions,
            extra_kwargs={
                "discard_audio_if_uninterruptible": False,
                "interruption_config": InterruptionConfig(),
            }
        )
        
        interruptions = []
        
        @session.on("agent_speech_interrupted")
        def on_interrupted(ev):
            interruptions.append(ev)
        
        await asyncio.wait_for(run_session(session, InterruptionTestAgent()), timeout=SESSION_TIMEOUT)
        
        # Assert: Command phrase was detected and interrupted
        assert len(interruptions) > 0, "Mixed utterance with command should interrupt"

    @pytest.mark.asyncio
    async def test_normal_content_interrupts_by_default(self):
        """User asks question while agent speaking → Interrupts (default policy)."""
        actions = FakeActions()
        
        actions.add_user_speech(0.5, 2.0, "Tell me about Paris")
        actions.add_llm("Paris is the capital...")
        actions.add_tts(10.0)
        
        # User asks different question during TTS
        actions.add_user_speech(3.0, 4.0, "What time is it?")
        
        session = create_session(
            actions,
            extra_kwargs={
                "discard_audio_if_uninterruptible": False,
                "interruption_config": InterruptionConfig(
                    interrupt_on_normal_content=True  # Default
                ),
            }
        )
        
        interruptions = []
        
        @session.on("agent_speech_interrupted")
        def on_interrupted(ev):
            interruptions.append(ev)
        
        await asyncio.wait_for(run_session(session, InterruptionTestAgent()), timeout=SESSION_TIMEOUT)
        
        # Assert: Normal content interrupted
        assert len(interruptions) > 0, "Normal content should interrupt by default"

    @pytest.mark.asyncio
    async def test_vad_disabled_in_semantic_mode(self):
        """VAD noise without meaningful text → No interruption."""
        actions = FakeActions()
        
        actions.add_user_speech(0.5, 2.0, "Tell me a story")
        actions.add_llm("Once upon a time in a faraway land...")
        actions.add_tts(15.0)
        
        # VAD detects noise but STT produces empty/noise text
        actions.add_user_speech(5.0, 5.2, "")  # Empty transcript
        
        session = create_session(
            actions,
            extra_kwargs={
                "discard_audio_if_uninterruptible": False,
                "interruption_config": InterruptionConfig(),
            }
        )
        
        interruptions = []
        
        @session.on("agent_speech_interrupted")
        def on_interrupted(ev):
            interruptions.append(ev)
        
        await asyncio.wait_for(run_session(session, InterruptionTestAgent()), timeout=SESSION_TIMEOUT)
        
        # Assert: No interruption (VAD path disabled, empty text swallowed)
        assert len(interruptions) == 0, "VAD noise without text should not interrupt"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
