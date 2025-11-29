"""State management for semantic interruption handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .classifier import InterruptionClassifier, UtteranceType

if TYPE_CHECKING:
    from ..agent_activity import AgentActivity
    from ..agent_session import AgentSession
    from .config import InterruptionConfig


class InterruptionController:
    """Manages interruption state and decisions for a single agent session.
    
    This controller is the central decision point for semantic interruption handling.
    It tracks utterance state, classifies user speech, and decides whether to:
    - Swallow backchannel events (no interruption, no user turn)
    - Trigger interruption for commands
    - Allow normal user turns
    
    The controller is stateful and tied to a single AgentSession lifecycle.
    
    Key responsibilities:
    - Track current utterance buffer
    - Prevent duplicate interruption triggers per utterance
    - Check agent speaking state before applying semantic filtering
    - Provide clean reset points for utterance lifecycle
    
    Example:
        >>> controller = InterruptionController(config, session, activity)
        >>> 
        >>> # On new user speech
        >>> controller.reset_utterance()
        >>> 
        >>> # On STT interim result
        >>> if controller.should_process_transcript("yeah", is_final=False):
        ...     # Pass through to user turn handling
        ...     pass
        >>> else:
        ...     # Swallow event
        ...     pass
    """
    
    def __init__(
        self,
        config: InterruptionConfig,
        session: AgentSession,
        agent_activity: AgentActivity,
    ):
        """Initialize controller for a session.
        
        Args:
            config: Interruption configuration with word lists and policies.
            session: Agent session to monitor for state.
            agent_activity: Activity to trigger interruptions on.
        """
        self.config = config
        self.classifier = InterruptionClassifier(config)
        self.session = session
        self.agent_activity = agent_activity
        
        # Utterance state tracking
        self._current_utterance_buffer = ""
        self._interruption_fired = False
    
    def reset_utterance(self) -> None:
        """Reset utterance state for new speech segment.
        
        This should be called:
        - When VAD detects start of speech (user_state → 'speaking')
        - When END_OF_SPEECH event fires
        - After final transcript is processed
        
        Resets:
        - Current utterance buffer
        - Interruption fired flag
        """
        self._current_utterance_buffer = ""
        self._interruption_fired = False
    
    def should_process_transcript(self, text: str, is_final: bool) -> bool:
        """Determine if transcript should create a user turn.
        
        This is the main decision point for semantic interruption handling.
        
        Logic:
        1. Update utterance buffer with latest text
        2. If agent not speaking → always pass through
        3. If agent is speaking:
           - Backchannel → swallow (return False)
           - Command → trigger interruption + pass through (return True)
           - Normal content → apply policy (interrupt_on_normal_content)
        
        Args:
            text: Latest STT text (interim or final).
            is_final: Whether this is a final transcript.
        
        Returns:
            True if transcript should be processed as user turn.
            False if transcript should be swallowed (backchannel while speaking).
        
        Side effects:
            May trigger interruption via agent_activity if command detected.
        """
        # Update buffer with latest text
        self._current_utterance_buffer = text
        
        # Check agent speaking state
        agent_speaking = self.session.agent_state == "speaking"
        
        if not agent_speaking:
            # Agent not speaking → pass through everything
            # User can say "yeah", "stop", or anything else and it becomes a normal turn
            return True
        
        # Agent IS speaking → apply semantic filtering
        utterance_type = self.classifier.classify(text)
        
        if utterance_type == UtteranceType.BACKCHANNEL:
            # Swallow backchannel utterances while agent is speaking
            # No interruption, no user turn
            return False
        
        elif utterance_type == UtteranceType.COMMAND:
            # Command detected → interrupt immediately
            if not self._interruption_fired:
                self._trigger_interruption()
                self._interruption_fired = True
            
            # Pass through to form user message
            return True
        
        elif utterance_type == UtteranceType.NORMAL:
            # Normal content → apply policy
            if self.config.interrupt_on_normal_content:
                # Default behavior: interrupt on any substantive utterance
                if not self._interruption_fired:
                    self._trigger_interruption()
                    self._interruption_fired = True
                return True
            else:
                # Alternative policy: ignore normal content while speaking
                # (rare use case, but configurable)
                return False
        
        # Fallback: pass through
        return True
    
    def _trigger_interruption(self) -> None:
        """Request interruption of current speech.
        
        This is called when a command or normal content (policy-dependent)
        is detected while the agent is speaking.
        """
        if self.agent_activity._current_speech:
            self.agent_activity._current_speech.interrupt()
