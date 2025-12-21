"""
Unit Tests for InterruptionController (Production-Ready)

Tests all scenarios including production fixes:
- Fix #1: Hyphen normalization ("uh-huh" → IGNORE)
- Fix #2: Multi-word phrase matching ("i see" → IGNORE)
- Fix #3: Grace period for state transitions
- Fix #4: Question words in INTERRUPT_WORDS
"""

import time
import pytest

from controller import Decision, InterruptionController, GRACE_PERIOD_SECONDS


class TestInterruptionController:
    """Test suite for InterruptionController."""
    
    def setup_method(self):
        """Create a fresh controller for each test."""
        self.controller = InterruptionController()
    
    # ==================== Test 1: Backchannel while speaking ====================
    
    def test_agent_speaking_yeah_ignored(self):
        """'yeah' while agent speaking should be IGNORED."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("yeah", is_final=True)
        assert decision == Decision.IGNORE
    
    def test_agent_speaking_ok_ignored(self):
        """'ok' while agent speaking should be IGNORED."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("ok", is_final=True)
        assert decision == Decision.IGNORE
    
    # ==================== Fix #1: Hyphen Normalization ====================
    
    def test_hyphenated_uh_huh_ignored(self):
        """'Uh-huh' with hyphen should be IGNORED (Fix #1)."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("Uh-huh", is_final=True)
        assert decision == Decision.IGNORE
    
    def test_hyphenated_mm_hmm_ignored(self):
        """'mm-hmm' with hyphen should be IGNORED (Fix #1)."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("mm-hmm", is_final=True)
        assert decision == Decision.IGNORE
    
    def test_hyphenated_with_punctuation_ignored(self):
        """'Uh-huh!' with hyphen and punctuation should be IGNORED."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("Uh-huh!", is_final=True)
        assert decision == Decision.IGNORE
    
    # ==================== Fix #2: Multi-word Phrase Matching ====================
    
    def test_multi_word_i_see_ignored(self):
        """'I see' multi-word phrase should be IGNORED (Fix #2)."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("I see", is_final=True)
        assert decision == Decision.IGNORE
    
    def test_multi_word_got_it_ignored(self):
        """'Got it' multi-word phrase should be IGNORED (Fix #2)."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("Got it", is_final=True)
        assert decision == Decision.IGNORE
    
    def test_multi_word_makes_sense_ignored(self):
        """'Makes sense' multi-word phrase should be IGNORED (Fix #2)."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("Makes sense", is_final=True)
        assert decision == Decision.IGNORE
    
    # ==================== Test 2: Command while speaking ====================
    
    def test_agent_speaking_stop_interrupts(self):
        """'stop' while agent speaking should INTERRUPT."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("stop", is_final=True)
        assert decision == Decision.INTERRUPT
    
    def test_agent_speaking_wait_interrupts(self):
        """'wait' while agent speaking should INTERRUPT."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("wait", is_final=True)
        assert decision == Decision.INTERRUPT
    
    def test_agent_speaking_hold_on_interrupts(self):
        """'hold on' multi-word command should INTERRUPT."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("hold on", is_final=True)
        assert decision == Decision.INTERRUPT
    
    # ==================== Fix #4: Question Words ====================
    
    def test_question_what_interrupts(self):
        """'what?' should INTERRUPT (Fix #4)."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("what?", is_final=True)
        assert decision == Decision.INTERRUPT
    
    def test_question_huh_interrupts(self):
        """'huh?' should INTERRUPT (Fix #4)."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("huh?", is_final=True)
        assert decision == Decision.INTERRUPT
    
    def test_question_pardon_interrupts(self):
        """'pardon?' should INTERRUPT (Fix #4)."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("pardon?", is_final=True)
        assert decision == Decision.INTERRUPT
    
    # ==================== Test 3: Input while silent ====================
    
    def test_agent_silent_yeah_no_decision(self):
        """'yeah' while agent silent should be NO_DECISION."""
        self.controller.update_agent_state("listening")
        # Wait for grace period to expire
        time.sleep(GRACE_PERIOD_SECONDS + 0.1)
        decision = self.controller.decide("yeah", is_final=True)
        assert decision == Decision.NO_DECISION
    
    def test_agent_idle_yeah_no_decision(self):
        """'yeah' while agent idle should be NO_DECISION."""
        self.controller.update_agent_state("idle")
        time.sleep(GRACE_PERIOD_SECONDS + 0.1)
        decision = self.controller.decide("yeah", is_final=True)
        assert decision == Decision.NO_DECISION
    
    # ==================== Fix #3: Grace Period ====================
    
    def test_grace_period_active(self):
        """Input during grace period should still be processed as if speaking."""
        self.controller.update_agent_state("speaking")
        self.controller.update_agent_state("listening")  # Agent just stopped
        
        # Immediately after (within grace period)
        decision = self.controller.decide("stop", is_final=True)
        assert decision == Decision.INTERRUPT  # Should still interrupt
    
    def test_grace_period_filler_ignored(self):
        """Filler during grace period should be IGNORED."""
        self.controller.update_agent_state("speaking")
        self.controller.update_agent_state("listening")  # Agent just stopped
        
        # Immediately after (within grace period)
        decision = self.controller.decide("yeah", is_final=True)
        assert decision == Decision.IGNORE  # Should still ignore filler
    
    def test_grace_period_expired(self):
        """After grace period, input should be NO_DECISION."""
        self.controller.update_agent_state("speaking")
        self.controller.update_agent_state("listening")
        
        # Wait for grace period to expire
        time.sleep(GRACE_PERIOD_SECONDS + 0.1)
        
        decision = self.controller.decide("yeah", is_final=True)
        assert decision == Decision.NO_DECISION
    
    # ==================== Test 4: Mixed input ====================
    
    def test_agent_speaking_yeah_but_wait_interrupts(self):
        """'yeah but wait' should INTERRUPT (detects 'but' and 'wait')."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("yeah but wait", is_final=True)
        assert decision == Decision.INTERRUPT
    
    def test_agent_speaking_ok_stop_interrupts(self):
        """'ok stop' should INTERRUPT (detects 'stop')."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("ok stop", is_final=True)
        assert decision == Decision.INTERRUPT
    
    # ==================== Test 5: Empty/noise ====================
    
    def test_empty_string_ignored(self):
        """Empty string should be IGNORED."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("", is_final=True)
        assert decision == Decision.IGNORE
    
    def test_whitespace_only_ignored(self):
        """Whitespace only should be IGNORED."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("   ", is_final=True)
        assert decision == Decision.IGNORE
    
    def test_punctuation_only_ignored(self):
        """Punctuation only should be IGNORED."""
        self.controller.update_agent_state("speaking")
        decision = self.controller.decide("...", is_final=True)
        assert decision == Decision.IGNORE
    
    # ==================== State tracking tests ====================
    
    def test_agent_state_transitions(self):
        """Test that agent state tracking works correctly."""
        assert self.controller.agent_speaking is False
        
        self.controller.update_agent_state("speaking")
        assert self.controller.agent_speaking is True
        
        self.controller.update_agent_state("listening")
        assert self.controller.agent_speaking is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
