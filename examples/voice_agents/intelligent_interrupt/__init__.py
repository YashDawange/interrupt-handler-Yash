"""
Intelligent Interrupt Module for LiveKit Voice Agents

This module provides context-aware interruption handling that distinguishes
between passive acknowledgements ("yeah", "ok") and active interruptions
("stop", "wait").

Quick Start:
    from intelligent_interrupt import attach_interrupt_handlers, get_session_options
    
    # Create session with recommended options
    session = AgentSession(
        llm=llm, stt=stt, tts=tts, vad=vad,
        **get_session_options(),
    )
    
    # Add interrupt handling - one line!
    attach_interrupt_handlers(session)
"""

from __future__ import annotations

# Core filter components
from .filter import (
    InterruptFilter,
    InterruptFilterConfig,
    InterruptAnalysis,
)

# Word lists
from .wordlists import (
    DEFAULT_IGNORE_WORDS,
    DEFAULT_INTERRUPT_WORDS,
)

# Session integration
from .session_integration import (
    get_session_options,
    attach_interrupt_handlers,
)

__all__ = [
    # Core filter
    "InterruptFilter",
    "InterruptFilterConfig", 
    "InterruptAnalysis",
    # Word lists
    "DEFAULT_IGNORE_WORDS",
    "DEFAULT_INTERRUPT_WORDS",
    # Session integration
