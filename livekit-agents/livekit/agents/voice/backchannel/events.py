"""
Backchannel Detection Events

Custom events for debugging, monitoring, and analytics of backchannel detection.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from .confidence import BackchannelConfidence


class BackchannelDetectedEvent(BaseModel):
    """
    Emitted when backchannel input is detected (regardless of decision).
    
    Provides full details of the detection and decision-making process.
    """
    
    type: str = "backchannel_detected"
    transcript: str
    confidence: dict[str, Any]  # BackchannelConfidence.to_dict()
    agent_speaking: bool
    decision: str  # "ignored" or "processed"
    reason: str  # Human-readable explanation
    created_at: float = Field(default_factory=time.time)
    
    class Config:
        frozen = True


class BackchannelDecisionEvent(BaseModel):
    """
    Emitted for every interruption decision (backchannel or not).
    
    Useful for A/B testing and accuracy measurement.
    """
    
    type: str = "backchannel_decision"
    transcript: str
    overall_confidence: float
    word_match_score: float
    prosody_score: float | None
    context_score: float
    user_history_score: float | None
    threshold: float
    decision: bool  # True = backchannel, False = command
    agent_speaking: bool
    features: dict[str, Any]
    created_at: float = Field(default_factory=time.time)
    
    class Config:
        frozen = True
    
    @classmethod
    def from_confidence(
        cls,
        confidence: BackchannelConfidence,
        agent_speaking: bool,
    ) -> BackchannelDecisionEvent:
        """Create event from confidence object."""
        return cls(
            transcript=confidence.transcript,
            overall_confidence=confidence.overall_score,
            word_match_score=confidence.word_match_score,
            prosody_score=confidence.prosody_score,
            context_score=confidence.context_score,
            user_history_score=confidence.user_history_score,
            threshold=confidence.threshold,
            decision=confidence.decision,
            agent_speaking=agent_speaking,
            features=confidence.features,
        )


class InterruptionPreventedEvent(BaseModel):
    """
    Emitted when an interruption was prevented due to backchannel detection.
    
    This is the key success metric for the feature.
    """
    
    type: str = "interruption_prevented"
    transcript: str
    confidence_score: float
    confidence_level: str  # "very_high", "high", "medium", "low", "very_low"
    agent_utterance_duration: float | None  # How long agent was speaking
    reasoning: str  # Why it was prevented
    created_at: float = Field(default_factory=time.time)
    
    class Config:
        frozen = True


class InterruptionAllowedEvent(BaseModel):
    """
    Emitted when an interruption was allowed (command detected).
    
    Useful for tracking interruption patterns and user behavior.
    """
    
    type: str = "interruption_allowed"
    transcript: str
    confidence_score: float
    confidence_level: str
    had_command_words: bool
    reasoning: str  # Why it was allowed
    created_at: float = Field(default_factory=time.time)
    
    class Config:
        frozen = True

