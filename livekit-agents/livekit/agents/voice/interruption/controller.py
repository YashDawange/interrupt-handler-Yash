"""State management for semantic interruption handling."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .classifier import InterruptionClassifier, UtteranceType

if TYPE_CHECKING:
    from ..agent_activity import AgentActivity
    from ..agent_session import AgentSession
    from .config import InterruptionConfig


logger = logging.getLogger(__name__)


@dataclass
class InterruptionDecision:
    """Result of an interruption decision with full context.
    
    This structured object allows for:
    - Clear logging and debugging
    - Metrics collection
    - Test assertions on decision reasoning
    
    Attributes:
        should_process: Whether transcript should create a user turn.
        should_interrupt: Whether to interrupt current agent speech.
        utterance_type: Classification of the utterance.
        reason: Human-readable explanation of the decision.
        matched_words: Words that influenced the decision (commands/backchannel).
    """
    should_process: bool
    should_interrupt: bool
    utterance_type: UtteranceType
    reason: str
    matched_words: list[str]


class InterruptionController:
    """Manages interruption state and decisions for a single agent session.
    
    This controller is the central decision point for semantic interruption handling.
    It tracks utterance state, classifies user speech, and decides whether to:
    - Swallow backchannel events (no interruption, no user turn)
    - Trigger interruption for commands
    - Allow normal user turns
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
        
        Args:
            text: Latest STT text (interim or final).
            is_final: Whether this is a final transcript.
        
        Returns:
            True if transcript should be processed as user turn.
            False if transcript should be swallowed (backchannel while speaking).
        """
        # Make decision using internal method
        decision = self._make_decision(text, is_final)
        
        # Log decision with full context
        transcript_type = "final" if is_final else "interim"
        logger.info(
            f"[SEMANTIC INTERRUPTION] {decision.utterance_type.value.upper()} | "
            f"Agent: {self.session.agent_state} | "
            f"Action: {'PROCESS' if decision.should_process else 'SWALLOW'} | "
            f"Interrupt: {decision.should_interrupt} | "
            f"Text: '{text[:50]}{'...' if len(text) > 50 else ''}' | "
            f"Type: {transcript_type} | "
            f"Reason: {decision.reason}"
        )
        
        if decision.matched_words:
            logger.debug(f"[SEMANTIC INTERRUPTION] Matched words: {decision.matched_words}")
        
        # Trigger interruption if needed
        if decision.should_interrupt and not self._interruption_fired:
            self._trigger_interruption(decision.reason)
            self._interruption_fired = True
        
        return decision.should_process
    
    def _make_decision(self, text: str, is_final: bool) -> InterruptionDecision:
        """Make interruption decision with full context.
        
        This internal method creates a structured decision object that
        can be logged, tested, and used for metrics.
        
        Args:
            text: Latest STT text.
            is_final: Whether this is final transcript.
        
        Returns:
            InterruptionDecision with full reasoning and context.
        """
        # Update buffer
        self._current_utterance_buffer = text
        
        # Check agent state
        agent_speaking = self.session.agent_state == "speaking"
        
        if not agent_speaking:
            # Not speaking → everything passes through as normal input
            return InterruptionDecision(
                should_process=True,
                should_interrupt=False,
                utterance_type=UtteranceType.NORMAL,
                reason=f"Agent is {self.session.agent_state}, processing as normal input",
                matched_words=[],
            )
        
        # Agent IS speaking → classify and decide
        utterance_type = self.classifier.classify(text)
        
        # Extract matched words for logging/debugging
        words = text.lower().split()
        matched_commands = [w for w in words if w in self.config.command_words]
        matched_backchannel = [w for w in words if w in self.config.ignore_words]
        
        if utterance_type == UtteranceType.BACKCHANNEL:
            return InterruptionDecision(
                should_process=False,  # Swallow backchannel to prevent LLM from generating a response that interrupts
                should_interrupt=False,  # But don't interrupt current speech
                utterance_type=UtteranceType.BACKCHANNEL,
                reason="Pure backchannel detected while agent speaking, swallowing event",
                matched_words=matched_backchannel,
            )
        
        elif utterance_type == UtteranceType.COMMAND:
            return InterruptionDecision(
                should_process=True,
                should_interrupt=True,
                utterance_type=UtteranceType.COMMAND,
                reason="Command word/phrase detected while agent speaking, interrupting",
                matched_words=matched_commands,
            )
        
        elif utterance_type == UtteranceType.NORMAL:
            if self.config.interrupt_on_normal_content:
                return InterruptionDecision(
                    should_process=True,
                    should_interrupt=True,
                    utterance_type=UtteranceType.NORMAL,
                    reason="Normal content while agent speaking (policy: interrupt)",
                    matched_words=[],
                )
            else:
                return InterruptionDecision(
                    should_process=False,
                    should_interrupt=False,
                    utterance_type=UtteranceType.NORMAL,
                    reason="Normal content while agent speaking (policy: ignore)",
                    matched_words=[],
                )
        
        # Fallback
        return InterruptionDecision(
            should_process=True,
            should_interrupt=False,
            utterance_type=UtteranceType.NORMAL,
            reason="Fallback: processing as normal input",
            matched_words=[],
        )
    
    def _trigger_interruption(self, reason: str = "semantic command") -> None:
        """Request interruption of current speech.
        
        This is called when a command or normal content (policy-dependent)
        is detected while the agent is speaking.
        
        Args:
            reason: Human-readable reason for interruption (for logging/metrics).
        """
        # Use public API instead of directly accessing _current_speech
        self.agent_activity.semantic_interrupt(reason)
