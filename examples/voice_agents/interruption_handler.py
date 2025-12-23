"""
Intelligent Interruption Handler for LiveKit Agents

This module implements the Temporal-Semantic Fusion (TSF) approach for handling
user interruptions in voice AI agents. It distinguishes between passive backchanneling
(e.g., "yeah", "ok") and active interruptions (e.g., "stop", "wait").

The handler ensures:
- Backchannels are IGNORED when the agent is speaking (no stutter/pause)
- Commands like "stop" or "wait" immediately interrupt the agent
- Mixed inputs like "Yeah but wait" trigger interruption (contains command)
- When agent is silent, ALL inputs are processed normally (including "yeah")
"""

import asyncio
import logging
import os
import string
from typing import Callable, Set

from livekit.agents import AgentSession, UserInputTranscribedEvent

logger = logging.getLogger("interruption-handler")


# Default list of words to ignore when the agent is speaking
# These are common backchanneling words that indicate the user is listening
DEFAULT_IGNORE_WORDS: Set[str] = {
    # Affirmative backchannels
    "yeah", "yes", "yea", "ya", "yep", "yup", "yah", "yeh",
    # Agreement/acknowledgment
    "ok", "okay", "k", "kk", "alright", "right", "sure", "fine",
    # Understanding signals
    "got it", "i see", "i understand", "understood",
    # Filler sounds / hesitations
    "hmm", "hm", "hmmmm", "aha", "ah", "uh", "um", "umm",
    "uh-huh", "uh huh", "mhm", "mhmm", "mm", "mmm", "mm-hmm",
    # Short encouragements
    "go on", "continue", "and", "so", "then",
}


def get_ignore_words() -> Set[str]:
    """
    Get the set of words to ignore when the agent is speaking.
    
    Can be configured via the IGNORE_WORDS environment variable as a comma-separated list.
    Falls back to DEFAULT_IGNORE_WORDS if not set.
    
    Returns:
        Set[str]: The set of words to ignore (all lowercase)
    """
    env_words = os.getenv("IGNORE_WORDS")
    if env_words:
        return {word.strip().lower() for word in env_words.split(",")}
    return DEFAULT_IGNORE_WORDS


def sanitize_transcript(text: str) -> str:
    """
    Sanitize the transcript text for comparison.
    
    - Converts to lowercase
    - Strips whitespace
    - Removes punctuation
    
    Args:
        text: The raw transcript text
        
    Returns:
        str: The sanitized text
    """
    text = text.lower().strip()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text


def is_backchannel(transcript: str, ignore_words: Set[str]) -> bool:
    """
    Check if the transcript consists entirely of backchannel words.
    
    Args:
        transcript: The sanitized transcript text
        ignore_words: The set of words to consider as backchannels
        
    Returns:
        bool: True if ALL words in the transcript are in the ignore list
    """
    if not transcript:
        return True  # Empty transcript is treated as backchannel (ignore)
    
    words = transcript.split()
    return all(word in ignore_words for word in words)


class InterruptionHandler:
    """
    Handles intelligent interruption logic for AgentSession.
    
    This class implements the Temporal-Semantic Fusion (TSF) approach:
    - Temporal: Checks if the agent is currently speaking
    - Semantic: Analyzes the transcript content to classify as backchannel or command
    
    Usage:
        handler = InterruptionHandler(session)
        handler.register()
        
    Or with custom ignore words:
        handler = InterruptionHandler(session, ignore_words={"yeah", "ok", "sure"})
        handler.register()
    """
    
    def __init__(
        self,
        session: AgentSession,
        ignore_words: Set[str] | None = None,
        on_backchannel: Callable[[str], None] | None = None,
        on_interrupt: Callable[[str], None] | None = None,
    ):
        """
        Initialize the interruption handler.
        
        Args:
            session: The AgentSession to attach the handler to
            ignore_words: Custom set of words to ignore (uses get_ignore_words() if None)
            on_backchannel: Optional callback when a backchannel is detected
            on_interrupt: Optional callback when an interruption is triggered
        """
        self.session = session
        self.ignore_words = ignore_words or get_ignore_words()
        self.on_backchannel = on_backchannel
        self.on_interrupt = on_interrupt
        self._registered = False
    
    def _handle_transcription(self, event: UserInputTranscribedEvent) -> None:
        """
        Handle the user_input_transcribed event.
        
        This implements the core TSF logic:
        1. Temporal Gate: If agent is NOT speaking, do nothing (let default behavior handle it)
        2. Semantic Filter: Check if transcript is backchannel or command
        3. Action: Ignore backchannels, interrupt for commands
        """
        # 1. Temporal Gate - Only filter when agent is speaking
        if self.session.agent_state != "speaking":
            # Agent is not speaking, treat all input as valid (including "yeah")
            print(f"[TSF] Agent silent - processing input: '{event.transcript}'")
            return
        
        # 2. Semantic Analysis
        transcript = sanitize_transcript(event.transcript)
        
        if not transcript:
            return
        
        # 3. Decision Matrix
        if is_backchannel(transcript, self.ignore_words):
            # Backchannel detected - IGNORE
            print(f"[TSF] IGNORED (backchannel): '{event.transcript}' - Agent continues speaking")
            if self.on_backchannel:
                self.on_backchannel(transcript)
            # Do nothing - agent continues speaking seamlessly
        else:
            # Active interruption detected - INTERRUPT
            print(f"[TSF] INTERRUPT: '{event.transcript}' - Stopping agent")
            if self.on_interrupt:
                self.on_interrupt(transcript)
            # Force interrupt the agent
            asyncio.create_task(self.session.interrupt(force=True))
    
    def register(self) -> "InterruptionHandler":
        """
        Register the handler with the session.
        
        Returns:
            self for method chaining
        """
        if not self._registered:
            self.session.on("user_input_transcribed", self._handle_transcription)
            self._registered = True
            logger.info("[TSF] Interruption handler registered")
        return self
    
    def unregister(self) -> "InterruptionHandler":
        """
        Unregister the handler from the session.
        
        Returns:
            self for method chaining
        """
        if self._registered:
            self.session.off("user_input_transcribed", self._handle_transcription)
            self._registered = False
            logger.info("[TSF] Interruption handler unregistered")
        return self


def setup_interruption_handler(
    session: AgentSession,
    ignore_words: Set[str] | None = None,
) -> InterruptionHandler:
    """
    Convenience function to set up the interruption handler.
    
    Args:
        session: The AgentSession to attach the handler to
        ignore_words: Custom set of words to ignore (uses environment or defaults if None)
        
    Returns:
        The registered InterruptionHandler instance
    """
    handler = InterruptionHandler(session, ignore_words=ignore_words)
    handler.register()
    return handler
