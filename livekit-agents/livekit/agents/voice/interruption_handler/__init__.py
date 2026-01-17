"""
LiveKit Intelligent Interruption Handler

A context-aware interruption handling system for LiveKit voice agents that
distinguishes between passive acknowledgments (backchanneling) and active
interruptions (commands).

Key Components:
- AgentStateManager: Tracks agent speaking state
- InterruptionFilter: Analyzes user input and decides whether to interrupt
- ConfigLoader: Loads configuration from files and environment variables

Usage Example:
    from livekit.agents.voice.interruption_handler import (
        AgentStateManager,
        InterruptionFilter,
        load_config,
    )
    
    # Initialize components
    state_mgr = AgentStateManager()
    config = load_config()
    filter = InterruptionFilter(
        ignore_words=config.ignore_words,
        command_words=config.command_words,
    )
    
    # When agent starts speaking
    await state_mgr.start_speaking(utterance_id="utt_123")
    
    # When user input is received
    should_interrupt, reason = filter.should_interrupt(
        text="yeah okay",
        agent_state=state_mgr.get_state().to_dict(),
    )
    
    if should_interrupt:
        await state_mgr.stop_speaking()
"""

from __future__ import annotations

from .config import ConfigLoader, InterruptionHandlerConfig, load_config
from .interruption_filter import InterruptionDecision, InterruptionFilter
from .state_manager import AgentStateManager, AgentStateSnapshot

__all__ = [
    # State Management
    "AgentStateManager",
    "AgentStateSnapshot",
    # Interruption Filtering
    "InterruptionFilter",
    "InterruptionDecision",
    # Configuration
    "InterruptionHandlerConfig",
    "ConfigLoader",
    "load_config",
]

__version__ = "1.0.0"
