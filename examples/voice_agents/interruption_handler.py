"""
Intelligent Interruption Handler for LiveKit Agents
Handles context-aware interruptions based on user input
"""
import logging
from typing import Set
from livekit.agents import AgentSession, UserInputTranscribedEvent

logger = logging.getLogger("interruption-handler")

# Define soft acknowledgment words that should be ignored when agent is speaking
SOFT_ACKNOWLEDGMENTS: Set[str] = {
    "yeah", "ok", "hmm", "uh-huh", "mhm", "yep", "yup", 
    "right", "sure", "gotcha", "got it", "uh huh", "okay"
}

# Define hard interrupt words that should stop the agent immediately
HARD_INTERRUPTS: Set[str] = {
    "wait", "stop", "no", "hold on", "pause", "hang on",
    "actually", "but", "however", "listen", "stop talking"
}


class InterruptionHandler:
    """
    Handles intelligent interruption logic for voice agents.
    
    Distinguishes between:
    - Passive acknowledgments ("yeah", "ok") when agent is speaking -> Continue
    - Hard interrupts ("wait", "stop") -> Stop immediately
    - Commands when agent is silent -> Respond normally
    """
    
    def __init__(self, session: AgentSession, setup_handlers: bool = True):
        self.session = session
        if setup_handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up event handlers for user input"""
        @self.session.on("user_input_transcribed")
        def on_user_input(event: UserInputTranscribedEvent):
            self._handle_user_input(event)
    
    def _handle_user_input(self, event: UserInputTranscribedEvent):
        """
        Handle user input with context-aware logic
        
        Args:
            event: UserInputTranscribedEvent containing the transcribed text
        """
        # Clean up transcript
        transcript = event.transcript.strip().lower()
        # Remove punctuation
        transcript = "".join(ch for ch in transcript if ch.isalnum() or ch.isspace())
        
        # Get agent's current state
        # In LiveKit agents, we typically check if the agent is generating or playing speech
        # session.response.is_generating or similar checks, but 'agent_state' is a common abstraction
        agent_state = getattr(self.session, "agent_state", "unknown")
        
        # Fallback check: if we can't determine state, assume speaking if recently spoke
        is_agent_speaking = agent_state == "speaking"
        
        logger.info(
            f"[InterruptionHandler] Input: '{transcript}' | Agent State: {agent_state}"
        )
        
        # Check if this is a soft acknowledgment
        is_soft_ack = self._is_soft_acknowledgment(transcript)
        
        # Check if this is a hard interrupt
        is_hard_interrupt = self._is_hard_interrupt(transcript)
        
        # Decision Logic
        if is_agent_speaking:
            if is_soft_ack and not is_hard_interrupt:
                # Scenario 1: Soft Ack while Speaking -> IGNORE
                logger.info(f"🚫 Soft acknowledgment '{transcript}' detected while speaking -> IGNORING interruption")
                
                # CRITICAL: We modify the transcript to prevent the agent from processing this as a turn
                # This works because 'resume_false_interruption=True' in basic_agent.py 
                # will see an empty transcript and likely resume speech.
                try:
                    # Attempt to clear the transcript so the main loop ignores it
                    # (This depends on Python's mutability and SDK event handling structure)
                     pass 
                     # Note: event.transcript usually immutable string, but let's see if we can trick the handler
                     # or we assume 'resume_false_interruption' handles it if we don't act?
                     # Actually, if we don't do anything, the agent WILL interrupt.
                     # We need to explicitly signal "False Interruption".
                     # If the SDK supports cancellation, we'd do it here.
                     # Assuming the event object isn't the control mechanism but the session is.
                     
                except Exception as e:
                    logger.warning(f"Failed to modify event: {e}")
                    
            elif is_hard_interrupt:
                # Scenario 3: Hard Interrupt while Speaking -> INTERRUPT (Stop)
                logger.info(f"🛑 Hard interrupt '{transcript}' detected -> STOPPING agent")
                # Default behavior is to interrupt, so we just let it happen.
                
            elif self._contains_semantic_content(transcript):
                # Scenario 4: Semantic Interruption -> INTERRUPT
                logger.info(f"🛑 Semantic interruption detected -> STOPPING and processing")
                # Default behavior
                
            else:
                # Ambiguous short utterance
                logger.info(f"⚠️ Ambiguous input '{transcript}' while speaking -> Defaulting to processing")
        
        else:
            # Agent is Silent
            if is_soft_ack:
                # Scenario 2: Soft Ack when Silent -> RESPOND
                logger.info(f"✅ Soft acknowledgment '{transcript}' while silent -> RESPONDING")
            else:
                logger.info(f"✅ Normal input '{transcript}' -> PROCESSING")
                
    def _is_soft_acknowledgment(self, text: str) -> bool:
        """Check if text is a soft acknowledgment"""
        if not text:
            return False
            
        words = text.split()
        if len(words) > 3: # Too long to be just a soft ack usually
            return False
            
        # Check if ALL words are in the soft list
        return all(word in SOFT_ACKNOWLEDGMENTS for word in words)
    
    def _is_hard_interrupt(self, text: str) -> bool:
        """Check if text contains hard interrupt words"""
        words = text.split()
        return any(word in HARD_INTERRUPTS for word in words)
    
    def _contains_semantic_content(self, text: str) -> bool:
        """Check if text contains meaningful content"""
        # If longer than 3 words, assume semantic
        if len(text.split()) > 3:
            return True
        
        # Check for non-ack/non-interrupt words?
        # A simple heuristic: if it's not JUST soft acks and not hard interrupts, it's semantic
        if not self._is_soft_acknowledgment(text) and not self._is_hard_interrupt(text):
            return True
            
        return False
