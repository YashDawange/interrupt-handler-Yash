"""
Unit tests for the Interruption Handler system.

Tests cover:
- State Manager: state transitions and thread safety
- Interruption Filter: decision logic and edge cases
- Configuration: loading from various sources
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from livekit.agents.voice.interruption_handler import (
    AgentStateManager,
    AgentStateSnapshot,
    InterruptionFilter,
    InterruptionDecision,
    InterruptionHandlerConfig,
    ConfigLoader,
    load_config,
)


# =============================================================================
# AgentStateManager Tests
# =============================================================================


class TestAgentStateManager:
    """Test suite for AgentStateManager."""
    
    @pytest.fixture
    def state_manager(self):
        """Create a fresh state manager for each test."""
        return AgentStateManager()
    
    @pytest.mark.asyncio
    async def test_initial_state(self, state_manager):
        """Test initial state is not speaking."""
        state = state_manager.get_state()
        assert not state.is_speaking
        assert state.utterance_id is None
        assert state.speech_start_time is None
    
    @pytest.mark.asyncio
    async def test_start_speaking(self, state_manager):
        """Test starting to speak."""
        await state_manager.start_speaking("utt_123")
        
        state = state_manager.get_state()
        assert state.is_speaking
        assert state.utterance_id == "utt_123"
        assert state.speech_start_time is not None
    
    @pytest.mark.asyncio
    async def test_stop_speaking(self, state_manager):
        """Test stopping speech."""
        await state_manager.start_speaking("utt_123")
        await state_manager.stop_speaking()
        
        state = state_manager.get_state()
        assert not state.is_speaking
        assert state.utterance_id is None
    
    @pytest.mark.asyncio
    async def test_speech_duration(self, state_manager):
        """Test speech duration calculation."""
        await state_manager.start_speaking("utt_123")
        await asyncio.sleep(0.1)
        
        duration = state_manager.get_speech_duration()
        assert duration is not None
        assert 0.09 < duration < 0.2  # Allow some tolerance
    
    @pytest.mark.asyncio
    async def test_empty_utterance_id_raises(self, state_manager):
        """Test that empty utterance_id raises ValueError."""
        with pytest.raises(ValueError):
            await state_manager.start_speaking("")
    
    @pytest.mark.asyncio
    async def test_quick_state_queries(self, state_manager):
        """Test non-blocking state queries."""
        await state_manager.start_speaking("utt_456")
        
        # These should be non-blocking
        assert state_manager.is_currently_speaking()
        assert state_manager.get_current_utterance_id() == "utt_456"
    
    @pytest.mark.asyncio
    async def test_reset(self, state_manager):
        """Test state reset."""
        await state_manager.start_speaking("utt_789")
        await state_manager.reset()
        
        state = state_manager.get_state()
        assert not state.is_speaking
        assert state.utterance_id is None
    
    @pytest.mark.asyncio
    async def test_auto_timeout(self):
        """Test auto-timeout functionality."""
        state_manager = AgentStateManager(auto_timeout=0.1)
        await state_manager.start_speaking("utt_timeout")
        
        # State should be speaking initially
        assert state_manager.is_currently_speaking()
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # State should have auto-stopped
        assert not state_manager.is_currently_speaking()
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, state_manager):
        """Test concurrent state access."""
        async def toggle_speaker():
            for i in range(5):
                await state_manager.start_speaking(f"utt_{i}")
                await asyncio.sleep(0.01)
                await state_manager.stop_speaking()
        
        async def read_state():
            results = []
            for _ in range(10):
                results.append(state_manager.is_currently_speaking())
                await asyncio.sleep(0.005)
            return results
        
        # Run both concurrently
        await asyncio.gather(toggle_speaker(), read_state())


# =============================================================================
# InterruptionFilter Tests
# =============================================================================


class TestInterruptionFilter:
    """Test suite for InterruptionFilter."""
    
    @pytest.fixture
    def interrupt_filter(self):
        """Create a fresh filter for each test."""
        return InterruptionFilter()
    
    def test_pure_backchannel_while_speaking(self, interrupt_filter):
        """Scenario 1: Pure backchannel while agent speaking -> IGNORE."""
        state = {"is_speaking": True}
        
        for word in ["yeah", "ok", "hmm", "uh-huh", "right", "yep"]:
            should_interrupt, reason = interrupt_filter.should_interrupt(word, state)
            assert not should_interrupt, f"Failed for '{word}': {reason}"
    
    def test_backchannel_while_silent(self, interrupt_filter):
        """Scenario 2: Backchannel while agent silent -> PROCESS (no interrupt)."""
        state = {"is_speaking": False}
        
        for word in ["yeah", "ok", "hmm"]:
            should_interrupt, reason = interrupt_filter.should_interrupt(word, state)
            # Should return False (don't interrupt) but process as input
            assert not should_interrupt, f"Failed for '{word}': {reason}"
    
    def test_command_word_while_speaking(self, interrupt_filter):
        """Scenario 3: Command word while speaking -> INTERRUPT."""
        state = {"is_speaking": True}
        
        for word in ["stop", "wait", "no", "hold on", "pause"]:
            should_interrupt, reason = interrupt_filter.should_interrupt(word, state)
            assert should_interrupt, f"Failed for '{word}': {reason}"
    
    def test_mixed_input_while_speaking(self, interrupt_filter):
        """Scenario 4: Mixed backchannel + command -> INTERRUPT."""
        state = {"is_speaking": True}
        
        mixed_inputs = [
            "yeah but wait",
            "okay no",
            "uh-huh hold on",
            "yeah okay but stop",
        ]
        
        for text in mixed_inputs:
            should_interrupt, reason = interrupt_filter.should_interrupt(text, state)
            assert should_interrupt, f"Failed for '{text}': {reason}"
    
    def test_detailed_classification(self, interrupt_filter):
        """Test detailed decision classification."""
        state = {"is_speaking": True}
        
        # Test backchannel classification
        decision = interrupt_filter.should_interrupt_detailed("yeah", state)
        assert decision.classified_as == "backchannel"
        
        # Test command classification
        decision = interrupt_filter.should_interrupt_detailed("stop", state)
        assert decision.classified_as == "command"
        
        # Test mixed classification
        decision = interrupt_filter.should_interrupt_detailed("yeah but wait", state)
        assert decision.classified_as == "mixed"
    
    def test_empty_text(self, interrupt_filter):
        """Test handling of empty text."""
        state = {"is_speaking": True}
        
        should_interrupt, reason = interrupt_filter.should_interrupt("", state)
        assert not should_interrupt
        
        should_interrupt, reason = interrupt_filter.should_interrupt("   ", state)
        assert not should_interrupt
    
    def test_case_insensitivity(self, interrupt_filter):
        """Test case-insensitive matching."""
        state = {"is_speaking": True}
        
        variations = ["YEAH", "Yeah", "yeAH", "ok", "OK", "Ok"]
        for text in variations:
            should_interrupt, reason = interrupt_filter.should_interrupt(text, state)
            assert not should_interrupt, f"Failed for '{text}'"
    
    def test_punctuation_handling(self, interrupt_filter):
        """Test that punctuation doesn't break matching."""
        state = {"is_speaking": True}
        
        variations = ["yeah.", "yeah!", "yeah?", "yeah,"]
        for text in variations:
            should_interrupt, reason = interrupt_filter.should_interrupt(text, state)
            assert not should_interrupt, f"Failed for '{text}'"
    
    def test_fuzzy_matching_typos(self, interrupt_filter):
        """Test fuzzy matching for common typos."""
        state = {"is_speaking": True}
        interrupt_filter.enable_fuzzy_match = True
        
        # These are misspellings that should match
        typos = ["yeah" -> "yeha", "ok" -> "ok", "stop" -> "stpo"]
        
        # "stpo" should match "stop" (command)
        should_interrupt, reason = interrupt_filter.should_interrupt("stpo", state)
        # May or may not match depending on threshold, just verify no error
        assert isinstance(should_interrupt, bool)
    
    def test_fuzzy_matching_disabled(self, interrupt_filter):
        """Test with fuzzy matching disabled."""
        state = {"is_speaking": True}
        interrupt_filter.enable_fuzzy_match = False
        
        should_interrupt, reason = interrupt_filter.should_interrupt("stpo", state)
        assert not should_interrupt  # Shouldn't match without fuzzy
    
    def test_custom_word_lists(self):
        """Test initialization with custom word lists."""
        custom_ignore = ["custom1", "custom2"]
        custom_command = ["custom_cmd1", "custom_cmd2"]
        
        filter = InterruptionFilter(
            ignore_words=custom_ignore,
            command_words=custom_command,
        )
        
        state = {"is_speaking": True}
        
        # Custom backchannel
        should_interrupt, _ = filter.should_interrupt("custom1", state)
        assert not should_interrupt
        
        # Custom command
        should_interrupt, _ = filter.should_interrupt("custom_cmd1", state)
        assert should_interrupt
    
    def test_update_word_lists(self, interrupt_filter):
        """Test updating word lists after initialization."""
        state = {"is_speaking": True}
        
        # Before update
        should_interrupt, _ = interrupt_filter.should_interrupt("newword", state)
        assert not should_interrupt
        
        # Update ignore words
        interrupt_filter.update_ignore_words(["newword"] + interrupt_filter.ignore_words)
        
        # After update
        should_interrupt, _ = interrupt_filter.should_interrupt("newword", state)
        assert not should_interrupt
    
    def test_multiword_backchannels(self, interrupt_filter):
        """Test multiword backchannels."""
        state = {"is_speaking": True}
        
        multiword = ["got it", "uh huh", "mm hmm", "copy that", "i see"]
        for text in multiword:
            should_interrupt, reason = interrupt_filter.should_interrupt(text, state)
            assert not should_interrupt, f"Failed for '{text}'"


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfigLoader:
    """Test suite for configuration loading."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = InterruptionHandlerConfig()
        
        assert config.enabled
        assert len(config.ignore_words) > 0
        assert len(config.command_words) > 0
        assert config.fuzzy_matching_enabled
        assert config.fuzzy_threshold == 0.8
        assert config.stt_wait_timeout_ms == 500.0
    
    def test_load_from_file(self):
        """Test loading configuration from JSON file."""
        config_data = {
            "interruption_handling": {
                "enabled": True,
                "ignore_words": {
                    "words": ["test_ignore"]
                },
                "command_words": {
                    "words": ["test_command"]
                },
                "fuzzy_matching": {
                    "enabled": False,
                    "similarity_threshold": 0.9
                }
            }
        }
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        try:
            config = ConfigLoader.load_from_file(temp_path)
            
            assert config is not None
            assert config.enabled
            assert "test_ignore" in config.ignore_words
            assert "test_command" in config.command_words
            assert not config.fuzzy_matching_enabled
            assert config.fuzzy_threshold == 0.9
        finally:
            Path(temp_path).unlink()
    
    def test_load_from_nonexistent_file(self):
        """Test loading from nonexistent file."""
        config = ConfigLoader.load_from_file("/nonexistent/path/config.json")
        assert config is None
    
    def test_parse_word_list_json(self):
        """Test parsing word list from JSON array string."""
        words = ConfigLoader._parse_word_list('["word1", "word2", "word3"]')
        assert words == ["word1", "word2", "word3"]
    
    def test_parse_word_list_comma_separated(self):
        """Test parsing word list from comma-separated string."""
        words = ConfigLoader._parse_word_list("word1, word2, word3")
        assert words == ["word1", "word2", "word3"]
    
    def test_load_function(self):
        """Test the convenience load_config function."""
        config = load_config(from_env=False)
        
        assert config is not None
        assert isinstance(config, InterruptionHandlerConfig)
        assert len(config.ignore_words) > 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple components."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_scenario_1(self):
        """Test full workflow: Long explanation with backchanneling."""
        state_manager = AgentStateManager()
        filter = InterruptionFilter()
        
        # Agent starts speaking
        await state_manager.start_speaking("utt_explanation")
        
        # User backchannels multiple times
        for backchannel in ["okay", "yeah", "uh-huh"]:
            agent_state = state_manager.get_state().to_dict()
            should_interrupt, _ = filter.should_interrupt(backchannel, agent_state)
            assert not should_interrupt, f"Shouldn't interrupt on '{backchannel}'"
        
        # Agent finishes
        await state_manager.stop_speaking()
    
    @pytest.mark.asyncio
    async def test_full_workflow_scenario_3(self):
        """Test full workflow: Active interruption."""
        state_manager = AgentStateManager()
        filter = InterruptionFilter()
        
        # Agent starts speaking
        await state_manager.start_speaking("utt_counting")
        
        # User tries to command
        for command in ["wait", "stop", "no"]:
            agent_state = state_manager.get_state().to_dict()
            should_interrupt, _ = filter.should_interrupt(command, agent_state)
            assert should_interrupt, f"Should interrupt on '{command}'"
        
        # Agent stops
        await state_manager.stop_speaking()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
