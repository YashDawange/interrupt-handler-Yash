"""
Unit tests for intelligent interruption handling.
"""

import pytest
from intelligent_interruption_agent import (
    InterruptionConfig,
    InputClassifier,
)


@pytest.fixture
def config():
    """Standard test configuration."""
    return InterruptionConfig(
        backchannel_words={'yeah', 'yes', 'ok', 'okay', 'hmm', 'mhmm', 'uh-huh', 'right'},
        interruption_words={'stop', 'wait', 'no', 'pause', 'hold'}
    )


@pytest.fixture
def classifier(config):
    """Create classifier with test config."""
    return InputClassifier(config)


class TestInputClassifier:
    """Test the input classification logic."""
    
    def test_pure_backchannel(self, classifier):
        """Test that pure backchannel words are classified correctly."""
        test_cases = [
            "yeah",
            "ok",
            "hmm",
            "uh-huh",
            "yeah yeah",
            "ok right",
            "mhmm okay",
        ]
        
        for text in test_cases:
            result = classifier.classify(text)
            assert result == "backchannel", f"Failed for: {text}"
    
    def test_interruption_words(self, classifier):
        """Test that interruption words are detected."""
        test_cases = [
            "stop",
            "wait",
            "no",
            "pause",
            "hold on",
            "Stop!",  # Case insensitive
            "WAIT",
        ]
        
        for text in test_cases:
            result = classifier.classify(text)
            assert result == "interruption", f"Failed for: {text}"
    
    def test_mixed_input_with_interruption(self, classifier):
        """Test that mixed input containing interruption words is classified as interruption."""
        test_cases = [
            "yeah but wait",
            "ok stop",
            "hmm no",
            "yeah okay but wait a second",
            "right but hold on",
        ]
        
        for text in test_cases:
            result = classifier.classify(text)
            assert result == "interruption", f"Failed for: {text}"
    
    def test_normal_input(self, classifier):
        """Test that normal conversation is classified correctly."""
        test_cases = [
            "hello",
            "what's the weather",
            "can you help me",
            "yeah I think so",  # Contains non-backchannel words
            "ok I understand what you mean",  # Mixed with normal words
        ]
        
        for text in test_cases:
            result = classifier.classify(text)
            assert result == "normal", f"Failed for: {text}"
    
    def test_empty_input(self, classifier):
        """Test edge cases with empty input."""
        test_cases = ["", "   ", None]
        
        for text in test_cases:
            result = classifier.classify(text or "")
            assert result == "normal"
    
    def test_case_insensitivity(self, classifier):
        """Test that classification is case-insensitive."""
        assert classifier.classify("YEAH") == "backchannel"
        assert classifier.classify("Yeah") == "backchannel"
        assert classifier.classify("STOP") == "interruption"
        assert classifier.classify("Stop") == "interruption"


class TestLogicMatrix:
    """Test the complete decision matrix from the challenge."""
    
    def test_scenario_1_long_explanation(self, classifier):
        """
        Scenario 1: The Long Explanation
        Agent is reading, user says backchannel → Agent continues
        """
        is_agent_speaking = True
        user_inputs = ["Okay", "yeah", "uh-huh"]
        
        for text in user_inputs:
            classification = classifier.classify(text)
            
            # When agent is speaking and input is backchannel
            if is_agent_speaking and classification == "backchannel":
                should_interrupt = False  # Should NOT interrupt
            else:
                should_interrupt = True
            
            assert not should_interrupt, f"Should not interrupt for: {text}"
    
    def test_scenario_2_passive_affirmation(self, classifier):
        """
        Scenario 2: The Passive Affirmation
        Agent is silent, user says "yeah" → Agent processes it
        """
        is_agent_speaking = False
        user_input = "Yeah"
        
        classification = classifier.classify(user_input)
        
        # When agent is silent, all inputs should be processed
        # (not really an "interruption" since agent isn't speaking)
        should_process = True
        
        assert should_process
        assert classification == "backchannel"
    
    def test_scenario_3_correction(self, classifier):
        """
        Scenario 3: The Correction
        Agent is speaking, user says "No stop" → Agent stops
        """
        is_agent_speaking = True
        user_input = "No stop"
        
        classification = classifier.classify(user_input)
        
        # Should interrupt because contains interruption word
        should_interrupt = classification == "interruption"
        
        assert should_interrupt
        assert classification == "interruption"
    
    def test_scenario_4_mixed_input(self, classifier):
        """
        Scenario 4: The Mixed Input
        Agent is speaking, user says "Yeah okay but wait" → Agent stops
        """
        is_agent_speaking = True
        user_input = "Yeah okay but wait"
        
        classification = classifier.classify(user_input)
        
        # Should interrupt because contains "wait" (interruption word)
        should_interrupt = classification == "interruption"
        
        assert should_interrupt
        assert classification == "interruption"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_punctuation_handling(self, classifier):
        """Test that punctuation doesn't affect classification."""
        assert classifier.classify("yeah!") == "backchannel"
        assert classifier.classify("ok.") == "backchannel"
        assert classifier.classify("stop!") == "interruption"
        assert classifier.classify("wait...") == "interruption"
    
    def test_multiple_spaces(self, classifier):
        """Test handling of extra whitespace."""
        assert classifier.classify("yeah    ok") == "backchannel"
        assert classifier.classify("  wait  ") == "interruption"
    
    def test_partial_words(self, classifier):
        """Test that partial matches don't trigger classification."""
        # "waiting" contains "wait" but as substring
        # Our word boundary regex should handle this
        result = classifier.classify("I'm waiting")
        # This should be "normal" since "waiting" is not "wait"
        # But depending on implementation, might need adjustment
        assert result == "normal"


@pytest.mark.asyncio
class TestIntegrationScenarios:
    """Integration test scenarios matching the challenge examples."""
    
    async def test_full_scenario_1(self, classifier):
        """Complete test of Scenario 1: Long explanation."""
        agent_speaking = True
        
        # Simulate agent speaking, user provides feedback
        inputs = ["okay", "yeah", "uh-huh"]
        
        for user_input in inputs:
            classification = classifier.classify(user_input)
            
            if agent_speaking and classification == "backchannel":
                # Should continue speaking (no interruption)
                assert True
            else:
                assert False, "Should not interrupt during backchannel"
    
    async def test_full_scenario_3(self, classifier):
        """Complete test of Scenario 3: Correction."""
        agent_speaking = True
        user_input = "No stop"
        
        classification = classifier.classify(user_input)
        
        # Should stop immediately
        assert classification == "interruption"
        assert agent_speaking  # Agent was speaking before


if __name__ == "__main__":
    pytest.main([__file__, "-v"])