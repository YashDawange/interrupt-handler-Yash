"""
Intelligent Interrupt Handler Module

This module provides semantic filtering for user speech during voice agent interactions,
eliminating audio pauses/stutters caused by backchannel words like "yeah", "ok", "hmm".
"""

from .controller import Decision, InterruptionController

__all__ = ["InterruptionController", "Decision"]
