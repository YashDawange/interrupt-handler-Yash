"""
Unit tests for the Intelligent Interruption Handler.

Tests cover:
1. Handler initialization and configuration
2. Agent speaking state tracking
3. VAD event handling
4. STT result analysis and decision logic
5. Environment variable configuration
6. Edge cases and error handling
"""

import asyncio
import os
from unittest.mock import patch

import pytest

from livekit.agents.voice.interruption_handler import (
    InterruptionDecision,
    InterruptionHandler,
    create_interruption_handler,
)


class TestInterruptionHandler:
    """Tests for InterruptionHandler class."""

    def test_initialization_default(self):
        """Test handler initializes with default word lists."""
        handler = InterruptionHandler()

        assert "yeah" in handler.ignore_words
        assert "ok" in handler.ignore_words
        assert "stop" in handler.command_words
        assert "wait" in handler.command_words
        assert not handler.agent_is_speaking

    def test_initialization_custom_words(self):
        """Test handler initializes with custom word lists."""
        ignore_words = frozenset(["yeah", "ok"])
        command_words = frozenset(["stop", "halt"])

        handler = InterruptionHandler(
            ignore_words=ignore_words,
            command_words=command_words,
        )

        assert handler.ignore_words == ignore_words
        assert handler.command_words == command_words

    def test_initialization_from_env_vars(self):
        """Test handler loads configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "LIVEKIT_IGNORE_WORDS": "yeah,ok,hmm",
                "LIVEKIT_COMMAND_WORDS": "stop,halt,cease",
            },
        ):
            handler = InterruptionHandler(enable_env_config=True)

            assert "yeah" in handler.ignore_words
            assert "ok" in handler.ignore_words
            assert "hmm" in handler.ignore_words
            assert "stop" in handler.command_words
            assert "halt" in handler.command_words
            assert "cease" in handler.command_words

    def test_agent_speaking_state_tracking(self):
        """Test agent speaking state is properly tracked."""
        handler = InterruptionHandler()

        assert not handler.agent_is_speaking

        handler.set_agent_speaking(True)
        assert handler.agent_is_speaking

        handler.set_agent_speaking(False)
        assert not handler.agent_is_speaking

    @pytest.mark.asyncio
    async def test_vad_event_when_agent_speaking(self):
        """Test VAD event when agent is speaking creates pending interrupt."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        decision = await handler.on_vad_event()

        assert not decision.should_interrupt
        assert decision.is_pending
        assert "pending" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_vad_event_when_agent_silent(self):
        """Test VAD event when agent is silent allows normal processing."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(False)

        decision = await handler.on_vad_event()

        assert decision.should_interrupt
        assert not decision.is_pending
        assert "silent" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_stt_ignore_filler_only(self):
        """Test STT result with only filler words is ignored."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        # Trigger pending interrupt
        await handler.on_vad_event()

        # Process filler-only transcript
        decision = await handler.on_stt_result("yeah")

        assert not decision.should_interrupt
        assert "filler" in decision.reason.lower() or "ignore" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_stt_ignore_multiple_fillers(self):
        """Test STT result with multiple filler words is ignored."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()

        decision = await handler.on_stt_result("yeah ok hmm")

        assert not decision.should_interrupt

    @pytest.mark.asyncio
    async def test_stt_command_interrupts(self):
        """Test STT result with command word triggers interruption."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()

        decision = await handler.on_stt_result("stop")

        assert decision.should_interrupt
        assert "command" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_stt_multiple_commands_interrupt(self):
        """Test STT result with multiple command words triggers interruption."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()

        decision = await handler.on_stt_result("wait no stop")

        assert decision.should_interrupt

    @pytest.mark.asyncio
    async def test_stt_mixed_input_interrupts(self):
        """Test STT result with mixed filler and command words triggers interruption."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()

        # "yeah but wait" should interrupt
        decision = await handler.on_stt_result("yeah but wait")

        assert decision.should_interrupt
        assert "command" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_stt_real_speech_interrupts(self):
        """Test STT result with real speech (not just fillers) triggers interruption."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()

        decision = await handler.on_stt_result("tell me more about that")

        assert decision.should_interrupt
        assert "real speech" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_stt_empty_transcript(self):
        """Test STT result with empty transcript is discarded."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()

        decision = await handler.on_stt_result("")

        assert not decision.should_interrupt

    @pytest.mark.asyncio
    async def test_stt_whitespace_only(self):
        """Test STT result with only whitespace is discarded."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()

        decision = await handler.on_stt_result("   ")

        assert not decision.should_interrupt

    @pytest.mark.asyncio
    async def test_stt_case_insensitive(self):
        """Test STT analysis is case-insensitive."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        # Test uppercase filler
        await handler.on_vad_event()
        decision = await handler.on_stt_result("YEAH")
        assert not decision.should_interrupt

        # Test uppercase command
        await handler.on_vad_event()
        decision = await handler.on_stt_result("STOP")
        assert decision.should_interrupt

        # Test mixed case
        await handler.on_vad_event()
        decision = await handler.on_stt_result("Yeah But WAIT")
        assert decision.should_interrupt

    @pytest.mark.asyncio
    async def test_stt_punctuation_handling(self):
        """Test STT properly handles punctuation in transcripts."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()
        decision = await handler.on_stt_result("yeah!")
        assert not decision.should_interrupt

        await handler.on_vad_event()
        decision = await handler.on_stt_result("stop!")
        assert decision.should_interrupt

        await handler.on_vad_event()
        decision = await handler.on_stt_result("yeah, ok.")
        assert not decision.should_interrupt

    @pytest.mark.asyncio
    async def test_stt_multi_word_commands(self):
        """Test STT properly detects multi-word commands like 'hold on'."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()
        decision = await handler.on_stt_result("hold on")
        assert decision.should_interrupt

        await handler.on_vad_event()
        decision = await handler.on_stt_result("hang on")
        assert decision.should_interrupt

    @pytest.mark.asyncio
    async def test_no_pending_interrupt(self):
        """Test STT result when there's no pending interrupt."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        # Call on_stt_result without calling on_vad_event first
        decision = await handler.on_stt_result("stop")

        assert not decision.should_interrupt
        assert "no pending" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_pending_interrupt_reset(self):
        """Test pending interrupt flag is properly reset after processing."""
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        # Set pending interrupt
        await handler.on_vad_event()

        # Process it
        await handler.on_stt_result("yeah")

        # Try to process another without new VAD event
        decision = await handler.on_stt_result("stop")
        assert not decision.should_interrupt  # Should not interrupt because no pending

    def test_reset_pending_interrupt(self):
        """Test manual reset of pending interrupt flag."""
        handler = InterruptionHandler()

        # Simulate internal state
        handler._pending_interrupt = True

        handler.reset_pending_interrupt()

        assert not handler._pending_interrupt

    @pytest.mark.asyncio
    async def test_scenario_agent_silent_filler(self):
        """
        Scenario 1: Agent silent + user says 'yeah' → process normally
        """
        handler = InterruptionHandler()
        handler.set_agent_speaking(False)

        decision = await handler.on_vad_event()

        assert decision.should_interrupt
        assert "silent" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_scenario_agent_speaking_filler(self):
        """
        Scenario 2: Agent speaking + user says 'yeah' → ignore
        """
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()
        decision = await handler.on_stt_result("yeah")

        assert not decision.should_interrupt

    @pytest.mark.asyncio
    async def test_scenario_agent_speaking_command(self):
        """
        Scenario 3: Agent speaking + user says 'stop' → interrupt
        """
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()
        decision = await handler.on_stt_result("stop")

        assert decision.should_interrupt

    @pytest.mark.asyncio
    async def test_scenario_agent_speaking_mixed(self):
        """
        Scenario 4: Agent speaking + user says 'yeah but wait' → interrupt
        """
        handler = InterruptionHandler()
        handler.set_agent_speaking(True)

        await handler.on_vad_event()
        decision = await handler.on_stt_result("yeah but wait")

        assert decision.should_interrupt


class TestCreateInterruptionHandler:
    """Tests for the create_interruption_handler factory function."""

    def test_create_with_defaults(self):
        """Test factory creates handler with default settings."""
        handler = create_interruption_handler()

        assert isinstance(handler, InterruptionHandler)
        assert len(handler.ignore_words) > 0
        assert len(handler.command_words) > 0

    def test_create_with_custom_lists(self):
        """Test factory creates handler with custom word lists."""
        ignore = ["yeah", "ok"]
        commands = ["stop", "halt"]

        handler = create_interruption_handler(
            ignore_words=ignore,
            command_words=commands,
        )

        assert handler.ignore_words == frozenset(["yeah", "ok"])
        assert handler.command_words == frozenset(["stop", "halt"])

    def test_create_with_env_config(self):
        """Test factory respects enable_env_config flag."""
        with patch.dict(
            os.environ,
            {
                "LIVEKIT_IGNORE_WORDS": "test1,test2",
                "LIVEKIT_COMMAND_WORDS": "cmd1,cmd2",
            },
        ):
            handler = create_interruption_handler(enable_env_config=True)

            assert "test1" in handler.ignore_words
            assert "cmd1" in handler.command_words


class TestInterruptionDecision:
    """Tests for InterruptionDecision dataclass."""

    def test_decision_creation(self):
        """Test creating an InterruptionDecision."""
        decision = InterruptionDecision(
            should_interrupt=True,
            reason="Test reason",
            is_pending=False,
        )

        assert decision.should_interrupt
        assert decision.reason == "Test reason"
        assert not decision.is_pending

    def test_decision_default_pending(self):
        """Test InterruptionDecision defaults is_pending to False."""
        decision = InterruptionDecision(
            should_interrupt=True,
            reason="Test",
        )

        assert not decision.is_pending


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
