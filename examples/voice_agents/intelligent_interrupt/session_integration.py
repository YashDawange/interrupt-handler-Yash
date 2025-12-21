"""
Session Integration - Plug-and-play integration with LiveKit AgentSession.

Usage:
    from intelligent_interrupt import attach_interrupt_handlers, get_session_options
    
    session = AgentSession(..., **get_session_options())
    attach_interrupt_handlers(session)
"""

from __future__ import annotations

import logging

from livekit.agents import AgentSession

try:
    from .filter import InterruptFilter
except ImportError:
    from filter import InterruptFilter

logger = logging.getLogger("intelligent-interrupt")


def get_session_options() -> dict:
    """
    Get the recommended session options for intelligent interrupt handling.
    
    Returns:
        Dict with allow_interruptions=True and min_interruption_words=999
    
    Usage:
        session = AgentSession(
            llm=llm, stt=stt, tts=tts, vad=vad,
            **get_session_options(),
        )
    """
    return {
        "allow_interruptions": True,  # Keep STT active during agent speech
        "min_interruption_words": 999,  # Block automatic audio-level interrupts
    }


def attach_interrupt_handlers(
    session: AgentSession,
    interrupt_filter: InterruptFilter | None = None,
    log_decisions: bool = True,
) -> dict:
    """
    Attach interrupt handling event handlers to a session.
    
    Args:
        session: The AgentSession to attach handlers to
        interrupt_filter: Optional custom filter (uses default if not provided)
        log_decisions: Whether to log filtering decisions
    
    Returns:
        A dict with state variables for advanced access
    
    Usage:
        session = AgentSession(..., **get_session_options())
        attach_interrupt_handlers(session)
    """
    filter_instance = interrupt_filter or InterruptFilter()
    
    # State tracking
    state = {
        "is_speaking": False,
        "handled_interrupt": False,
    }
    
    @session.on("agent_state_changed")
    def on_agent_state_changed(ev) -> None:
        state["is_speaking"] = ev.new_state == "speaking"
        if log_decisions:
            logger.debug(f"Agent state: {ev.old_state} -> {ev.new_state}")
    
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev) -> None:
        transcript = ev.transcript.strip()
        if not transcript:
            return
        
        # Reset on final transcript
        if ev.is_final:
            state["handled_interrupt"] = False
        
        # Analyze transcript
        analysis = filter_instance.analyze(transcript, state["is_speaking"])
        
        # Handle interrupt decision
        if analysis.decision == "interrupt" and state["is_speaking"]:
            if not state["handled_interrupt"]:
                current_speech = session.current_speech
                if current_speech and not current_speech.interrupted:
                    if log_decisions:
                        logger.info(f"[INTERRUPT] '{transcript}' - {analysis.reason}")
                    current_speech.interrupt(force=True)
                    state["handled_interrupt"] = True
        elif ev.is_final and log_decisions:
            if analysis.decision == "ignore":
                logger.info(f"[IGNORED] '{transcript}'")
            else:
                logger.info(f"[RESPOND] '{transcript}'")
    
    return state
