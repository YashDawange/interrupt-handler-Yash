"""Tests for smart interruption filtering functionality."""

import time

import pytest

from livekit.agents.voice import (
    DEFAULT_BACKCHANNEL_WORDS,
    DEFAULT_INTERRUPT_KEYWORDS,
    InterruptionConfig,
    InterruptionDecision,
    InterruptionFilter,
)
from livekit.agents.vad import VADEvent, VADEventType


class TestInterruptionConfig:
    """Test cases for InterruptionConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = InterruptionConfig()

        # Check defaults are loaded
        assert len(config.backchannel_words) > 0
        assert len(config.interrupt_keywords) > 0
        assert config.stt_timeout == 0.5
        assert config.case_sensitive is False

        # Check some expected words
        assert "yeah" in config.backchannel_words
        assert "ok" in config.backchannel_words
        assert "wait" in config.interrupt_keywords
        assert "stop" in config.interrupt_keywords

    def test_custom_config(self):
        """Test custom configuration."""
        custom_backchannels = {"yeah", "ok", "hmm"}
        custom_interrupts = {"wait", "stop"}

        config = InterruptionConfig(
            backchannel_words=custom_backchannels,
            interrupt_keywords=custom_interrupts,
            stt_timeout=0.3,
            case_sensitive=True,
        )

        assert config.backchannel_words == custom_backchannels
        assert config.interrupt_keywords == custom_interrupts
        assert config.stt_timeout == 0.3
        assert config.case_sensitive is True

    def test_invalid_timeout(self):
        """Test that invalid timeout raises ValueError."""
        with pytest.raises(ValueError, match="stt_timeout must be positive"):
            InterruptionConfig(stt_timeout=0)

        with pytest.raises(ValueError, match="stt_timeout must be positive"):
            InterruptionConfig(stt_timeout=-1)


class TestInterruptionFilter:
    """Test cases for InterruptionFilter."""

    def test_is_only_backchannel(self):
        """Test detection of backchannel-only input."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Only backchannel words
        assert filter._is_only_backchannel(["yeah"]) is True
        assert filter._is_only_backchannel(["yeah", "ok"]) is True
        assert filter._is_only_backchannel(["hmm", "uh-huh"]) is True

        # Mixed input
        assert filter._is_only_backchannel(["yeah", "wait"]) is False
        assert filter._is_only_backchannel(["hello"]) is False
        assert filter._is_only_backchannel(["yeah", "but", "wait"]) is False

        # Empty
        assert filter._is_only_backchannel([]) is False

    def test_contains_interrupt_keyword(self):
        """Test detection of interrupt keywords."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Contains interrupt keywords
        assert filter._contains_interrupt_keyword(["wait"]) is True
        assert filter._contains_interrupt_keyword(["stop"]) is True
        assert filter._contains_interrupt_keyword(["yeah", "wait"]) is True
        assert filter._contains_interrupt_keyword(["hold", "on"]) is True

        # No interrupt keywords
        assert filter._contains_interrupt_keyword(["yeah"]) is False
        assert filter._contains_interrupt_keyword(["ok", "hmm"]) is False

        # Empty
        assert filter._contains_interrupt_keyword([]) is False

    def test_analyze_transcript_only_backchannel(self):
        """Test transcript analysis for backchannel-only input."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Only backchannel
        assert filter._analyze_transcript("yeah") == InterruptionDecision.IGNORE
        assert filter._analyze_transcript("ok") == InterruptionDecision.IGNORE
        assert filter._analyze_transcript("yeah ok") == InterruptionDecision.IGNORE
        assert filter._analyze_transcript("hmm right") == InterruptionDecision.IGNORE

    def test_analyze_transcript_with_interrupt(self):
        """Test transcript analysis with interrupt keywords."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Contains interrupt keywords
        assert filter._analyze_transcript("wait") == InterruptionDecision.INTERRUPT
        assert filter._analyze_transcript("stop") == InterruptionDecision.INTERRUPT
        assert filter._analyze_transcript("yeah wait") == InterruptionDecision.INTERRUPT
        assert filter._analyze_transcript("yeah but wait") == InterruptionDecision.INTERRUPT

    def test_analyze_transcript_mixed_unknown(self):
        """Test transcript analysis with mixed/unknown input."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Unknown words (conservative: interrupt)
        assert filter._analyze_transcript("hello") == InterruptionDecision.INTERRUPT
        assert filter._analyze_transcript("yeah hello") == InterruptionDecision.INTERRUPT

    def test_analyze_transcript_empty(self):
        """Test transcript analysis with empty input."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Empty transcript
        assert filter._analyze_transcript("") == InterruptionDecision.IGNORE
        assert filter._analyze_transcript("   ") == InterruptionDecision.IGNORE

    def test_case_sensitivity(self):
        """Test case sensitivity in word matching."""
        # Case insensitive (default)
        config = InterruptionConfig(case_sensitive=False)
        filter = InterruptionFilter(config)
        assert filter._is_only_backchannel(["YEAH"]) is True
        assert filter._contains_interrupt_keyword(["WAIT"]) is True

        # Case sensitive
        config_cs = InterruptionConfig(case_sensitive=True)
        filter_cs = InterruptionFilter(config_cs)
        # Default words are lowercase, so uppercase won't match
        assert filter_cs._is_only_backchannel(["YEAH"]) is False

    @pytest.mark.asyncio
    async def test_vad_event_when_agent_speaking(self):
        """Test VAD event handling when agent is speaking."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Set agent state to speaking
        filter.update_agent_state("speaking")

        # Create VAD event
        vad_event = VADEvent(
            type=VADEventType.START_OF_SPEECH,
            samples_index=0,
            timestamp=time.time(),
            speech_duration=0.5,
            silence_duration=0.0,
            probability=0.9,
            frames=[],
        )

        # Should buffer the event (return PENDING)
        decision, processed_event = await filter.on_vad_event(vad_event)
        assert decision == InterruptionDecision.PENDING
        assert processed_event is None
        assert filter.get_pending_count() == 1

        # Clean up - cancel pending tasks
        await filter.aclose()

    @pytest.mark.asyncio
    async def test_vad_event_when_agent_silent(self):
        """Test VAD event handling when agent is not speaking."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Set agent state to listening
        filter.update_agent_state("listening")

        # Create VAD event
        vad_event = VADEvent(
            type=VADEventType.START_OF_SPEECH,
            samples_index=0,
            timestamp=time.time(),
            speech_duration=0.5,
            silence_duration=0.0,
            probability=0.9,
            frames=[],
        )

        # Should pass through (return RESPOND)
        decision, processed_event = await filter.on_vad_event(vad_event)
        assert decision == InterruptionDecision.RESPOND
        assert processed_event == vad_event

    @pytest.mark.asyncio
    async def test_stt_event_ignore_backchannel(self):
        """Test STT event handling for backchannel words."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Set up pending interruption
        filter.update_agent_state("speaking")
        vad_event = VADEvent(
            type=VADEventType.START_OF_SPEECH,
            samples_index=0,
            timestamp=time.time(),
            speech_duration=0.5,
            silence_duration=0.0,
            probability=0.9,
            frames=[],
        )
        await filter.on_vad_event(vad_event)

        # Analyze backchannel transcript
        decision = await filter.on_stt_event("yeah", is_final=True)
        assert decision == InterruptionDecision.IGNORE
        assert filter.get_pending_count() == 0  # Pending cleared

    @pytest.mark.asyncio
    async def test_stt_event_interrupt(self):
        """Test STT event handling for interrupt keywords."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Set up pending interruption
        filter.update_agent_state("speaking")
        vad_event = VADEvent(
            type=VADEventType.START_OF_SPEECH,
            samples_index=0,
            timestamp=time.time(),
            speech_duration=0.5,
            silence_duration=0.0,
            probability=0.9,
            frames=[],
        )
        await filter.on_vad_event(vad_event)

        # Analyze interrupt transcript
        decision = await filter.on_stt_event("wait", is_final=True)
        assert decision == InterruptionDecision.INTERRUPT
        assert filter.get_pending_count() == 0  # Pending cleared

    @pytest.mark.asyncio
    async def test_stt_event_mixed_input(self):
        """Test STT event handling for mixed input."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Set up pending interruption
        filter.update_agent_state("speaking")
        vad_event = VADEvent(
            type=VADEventType.START_OF_SPEECH,
            samples_index=0,
            timestamp=time.time(),
            speech_duration=0.5,
            silence_duration=0.0,
            probability=0.9,
            frames=[],
        )
        await filter.on_vad_event(vad_event)

        # Analyze mixed transcript (contains interrupt keyword)
        decision = await filter.on_stt_event("yeah but wait", is_final=True)
        assert decision == InterruptionDecision.INTERRUPT
        assert filter.get_pending_count() == 0

    @pytest.mark.asyncio
    async def test_state_change_clears_pending(self):
        """Test that state changes clear pending interruptions."""
        config = InterruptionConfig()
        filter = InterruptionFilter(config)

        # Set up pending interruption
        filter.update_agent_state("speaking")
        vad_event = VADEvent(
            type=VADEventType.START_OF_SPEECH,
            samples_index=0,
            timestamp=time.time(),
            speech_duration=0.5,
            silence_duration=0.0,
            probability=0.9,
            frames=[],
        )
        await filter.on_vad_event(vad_event)
        assert filter.get_pending_count() == 1

        # Change state to listening
        filter.update_agent_state("listening")

        # Give it a moment to clear
        import asyncio

        await asyncio.sleep(0.01)

        # Pending should be cleared
        assert filter.get_pending_count() == 0
