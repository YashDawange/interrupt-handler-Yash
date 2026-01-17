"""
Custom Turn Detector for Intelligent Interruption Handling

This module provides a custom turn detector that prevents the agent from
being interrupted by passive acknowledgments like "yeah", "ok", "hmm".
"""

import asyncio
import logging
from typing import Set
from livekit import agents, rtc

logger = logging.getLogger(__name__)


class PassiveFilterTurnDetector:
    """
    A turn detector wrapper that filters out passive acknowledgments
    to prevent unwanted interruptions.
    """
    
    def __init__(
        self,
        base_detector,
        ignore_words: Set[str] = None,
        interrupt_words: Set[str] = None,
        min_interruption_duration: float = 0.8,
    ):
        """
        Args:
            base_detector: The underlying turn detector (e.g., MultilingualModel)
            ignore_words: Set of words to ignore when agent is speaking
            min_interruption_duration: Minimum duration (seconds) of speech to trigger interrupt
        """
        self._base_detector = base_detector
        self._ignore_words = ignore_words or {
            'yeah', 'ok', 'okay', 'hmm', 'uh-huh', 'right', 
            'aha', 'mhm', 'mm-hmm', 'sure', 'yep', 'yes',
            'got it', 'i see', 'understand', 'alright'
        }
        self._interrupt_words = interrupt_words or {
            'wait', 'stop', 'no', 'hold', 'pause',
            'hang on', 'hold on', 'actually', 'but'
        }
        self._min_interruption_duration = min_interruption_duration
        
        # State tracking
        self._agent_speaking = False
        self._user_speech_start = None
        self._latest_transcription = ""
        
    async def detect_turn(self, *args, **kwargs):
        """Delegate to base detector"""
        return await self._base_detector.detect_turn(*args, **kwargs)
    
    def set_agent_speaking(self, speaking: bool):
        """Update agent speaking state"""
        self._agent_speaking = speaking
        logger.debug(f"Agent speaking: {speaking}")
    
    def should_interrupt(self, transcription: str = None, duration: float = 0) -> bool:
        """
        Determine if the current user speech should interrupt the agent.
        
        Args:
            transcription: The transcribed text (if available)
            duration: Duration of user speech in seconds
            
        Returns:
            True if should interrupt, False otherwise
        """
        # If agent is not speaking, always allow
        if not self._agent_speaking:
            return True
        
        # If we have transcription, analyze it
        if transcription:
            self._latest_transcription = transcription
            normalized = transcription.lower().strip()
            words = normalized.split()
            
            # Check for interrupt words first (highest priority)
            for interrupt_word in self._interrupt_words:
                if interrupt_word in normalized:
                    logger.info(f"✓ Interrupt allowed (contains '{interrupt_word}'): {transcription}")
                    return True
            
            # Check if purely passive
            is_passive = all(word in self._ignore_words for word in words if word)
            
            if is_passive:
                logger.info(f"✗ Interrupt blocked (passive): {transcription}")
                return False
            
            # Has non-passive content
            logger.info(f"✓ Interrupt allowed (non-passive): {transcription}")
            return True
        
        # No transcription yet - use duration heuristic
        # Very short utterances are likely passive acknowledgments
        if duration < self._min_interruption_duration:
            logger.debug(f"✗ Interrupt blocked (too short: {duration:.2f}s)")
            return False
        
        # Longer utterance without transcription - allow
        logger.debug(f"✓ Interrupt allowed (duration: {duration:.2f}s)")
        return True


def create_filtered_turn_detector(ignore_words=None, interrupt_words=None):
    """
    Factory function to create a filtered turn detector.
    
    Returns:
        A configured PassiveFilterTurnDetector
    """
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    
    base_detector = MultilingualModel()
    
    return PassiveFilterTurnDetector(
        base_detector=base_detector,
        ignore_words=ignore_words,
        interrupt_words=interrupt_words,
    )