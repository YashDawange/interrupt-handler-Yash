"""Semantic interruption handling for LiveKit Agents.

This module provides intelligent interruption control that distinguishes between
passive backchannel feedback ("yeah", "ok", "hmm") and active interruptions
("stop", "wait") based on the agent's speaking state.
"""

from .classifier import InterruptionClassifier, UtteranceType
from .config import InterruptionConfig
from .controller import InterruptionController

__all__ = [
    "InterruptionConfig",
    "InterruptionClassifier",
    "UtteranceType",
    "InterruptionController",
]
