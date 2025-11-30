"""Semantic interruption handling for LiveKit Agents.

This module provides intelligent interruption control that distinguishes between
passive backchannel feedback and active interruptions based on conversation context.

Key exports:
    InterruptionConfig: Configuration for word lists and policies
    InterruptionClassifier: Text classification (backchannel vs command vs normal)
    UtteranceType: Enum for classification results
    InterruptionController: State management and decision making
    InterruptionDecision: Structured decision object with reasoning
"""

from .classifier import InterruptionClassifier, UtteranceType
from .config import InterruptionConfig
from .controller import InterruptionController, InterruptionDecision

__all__ = [
    "InterruptionConfig",
    "InterruptionClassifier",
    "UtteranceType",
    "InterruptionController",
    "InterruptionDecision",
]
