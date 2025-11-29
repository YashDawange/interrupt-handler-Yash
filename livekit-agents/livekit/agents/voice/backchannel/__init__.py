"""
Advanced Backchannel Detection System

This module provides intelligent, multi-modal backchannel detection with:
- Confidence scoring (text, audio, context, user history)
- Audio feature analysis (prosody, tone, pitch)
- ML-based intent classification
- Per-user adaptive learning
- Comprehensive metrics and debugging

The system uses a layered approach with graceful degradation:
1. ML Classifier (if available)
2. Audio Feature Analysis (if audio accessible)
3. Enhanced Word Matching (always available)
4. Traditional Interruption (safe default)
"""

from .confidence import BackchannelConfidence, ConfidenceScorer
from .events import (
    BackchannelDetectedEvent,
    BackchannelDecisionEvent,
    InterruptionAllowedEvent,
    InterruptionPreventedEvent,
)

__all__ = [
    "BackchannelConfidence",
    "ConfidenceScorer",
    "BackchannelDetectedEvent",
    "BackchannelDecisionEvent",
    "InterruptionAllowedEvent",
    "InterruptionPreventedEvent",
]

