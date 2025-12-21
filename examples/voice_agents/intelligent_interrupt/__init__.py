"""
Intelligent Interruption Handling Module

This module provides context-aware interruption filtering for LiveKit voice agents.
It distinguishes between passive acknowledgements and active interruptions based
on the agent's current speaking state.

Example Usage:
    from intelligent_interrupt import InterruptFilter, InterruptFilterConfig
    
    # Create filter with custom config
    config = InterruptFilterConfig(
        ignore_words=frozenset(["yeah", "ok", "hmm"]),
        interrupt_words=frozenset(["stop", "wait", "no"])
    )
    filter = InterruptFilter(config)
    
    # Analyze user input
    analysis = filter.analyze("yeah okay", agent_speaking=True)
    print(analysis.decision)  # "ignore"
    
    analysis = filter.analyze("stop please", agent_speaking=True)
    print(analysis.decision)  # "interrupt"
"""

from .interrupt_filter import (
    InterruptFilter,
    InterruptFilterConfig,
    InterruptAnalysis,
    InterruptDecision,
    DEFAULT_IGNORE_WORDS,
    DEFAULT_INTERRUPT_WORDS,
    get_default_filter,
    set_default_filter,
)

__all__ = [
    "InterruptFilter",
    "InterruptFilterConfig",
    "InterruptAnalysis",
    "InterruptDecision",
    "DEFAULT_IGNORE_WORDS",
    "DEFAULT_INTERRUPT_WORDS",
    "get_default_filter",
    "set_default_filter",
]
