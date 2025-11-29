#!/usr/bin/env python3

import asyncio
import logging
import re
from typing import Set

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("intelligent-interruption-demo")


class IntelligentInterruptionHandler:
    """
    Handles intelligent interruption logic based on agent state and user input.
    
    This class distinguishes between passive acknowledgments (like "yeah", "ok", "hmm")
    and active interruptions (like "wait", "stop", "no") based on whether the agent
    is currently speaking or silent.
    """
    
    def __init__(self):
        self.ignore_list: Set[str] = {
            'yeah', 'ok', 'hmm', 'right', 'uh-huh', 'yep', 'yup', 'aha', 'mmm', 'got it',
            'i see', 'i know', 'sure', 'okay', 'yes', 'yuppers', 'uhuh', 'mhm'
        }
        self.interrupt_list: Set[str] = {
            'wait', 'stop', 'no', 'cancel', 'hold on', 'please stop', 'never mind',
            'shut up', 'quiet', 'silence'
        }
        
    def should_ignore_input(self, text: str, agent_speaking: bool) -> bool:
        """
        Determines if user input should be ignored based on agent state and input content.
        
        Args:
            text: The user's transcribed input
            agent_speaking: Whether the agent is currently speaking
            
        Returns:
            True if the input should be ignored, False otherwise
        """
        normalized_text = self._normalize_text(text)
        
        if not agent_speaking:
            return False
            
        words = normalized_text.split()
        
        if len(words) == 1 and words[0] in self.ignore_list:
            return True
            
        for word in words:
            if word in self.interrupt_list:
                return False
                
        all_passive = all(word in self.ignore_list for word in words)
        return all_passive and agent_speaking
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison by lowercasing and removing punctuation."""
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = ' '.join(normalized.split())
        return normalized


class MockAgentSession:
    """Mock agent session to simulate agent states."""
    
    def __init__(self):
        self.agent_state = "listening"  
        
    def set_agent_state(self, state: str):
        """Set the agent state (speaking or listening)."""
        self.agent_state = state
        logger.info(f"Agent state changed to: {state}")


class MockAgentActivity:
    """Mock agent activity to demonstrate the interruption handling."""
    
    def __init__(self, session: MockAgentSession):
        self.session = session
        self.interruption_handler = IntelligentInterruptionHandler()
        
    def on_end_of_turn(self, user_input: str) -> bool:
        """
        Simulate the on_end_of_turn method with intelligent interruption handling.
        
        Args:
            user_input: The user's transcribed input
            
        Returns:
            True if the input was handled (ignored or processed), False otherwise
        """
        agent_speaking = self.session.agent_state == "speaking"
        
       
        should_ignore = self.interruption_handler.should_ignore_input(user_input, agent_speaking)
        
        logger.info(
            f"User input: '{user_input}', Agent state: {self.session.agent_state}, "
            f"Should ignore: {should_ignore}"
        )
        
        if should_ignore and agent_speaking:
            logger.info(f"IGNORED: Passive acknowledgment '{user_input}' while agent is speaking")
           
            return True
            
        if agent_speaking:
            logger.info(f"INTERRUPT: Processing '{user_input}' as active interruption")
            self.session.set_agent_state("listening")
        else:
            logger.info(f"PROCESS: Processing '{user_input}' as normal input")
            
        return False


async def simulate_conversation():
    """Simulate a conversation to demonstrate the intelligent interruption handling."""
    
    logger.info("=== Intelligent Interruption Handler Demonstration ===")
    
    session = MockAgentSession()
    activity = MockAgentActivity(session)
    
    scenarios = [
        ("Agent starts speaking a long response...", lambda: session.set_agent_state("speaking")),
        ("User says 'yeah' while agent is speaking", lambda: activity.on_end_of_turn("yeah")),
        ("User says 'ok' while agent is speaking", lambda: activity.on_end_of_turn("ok")),
        ("User says 'hmm' while agent is speaking", lambda: activity.on_end_of_turn("hmm")),
        ("User says 'yeah ok hmm' while agent is speaking", lambda: activity.on_end_of_turn("yeah ok hmm")),
        
        ("Agent finishes speaking", lambda: session.set_agent_state("listening")),
        ("User says 'yeah' while agent is listening", lambda: activity.on_end_of_turn("yeah")),
        ("User says 'ok' while agent is listening", lambda: activity.on_end_of_turn("ok")),
        
        ("Agent starts speaking again", lambda: session.set_agent_state("speaking")),
        ("User says 'stop' while agent is speaking", lambda: activity.on_end_of_turn("stop")),
        
        ("Agent starts speaking again", lambda: session.set_agent_state("speaking")),
        ("User says 'yeah wait' while agent is speaking", lambda: activity.on_end_of_turn("yeah wait")),
        
        ("Agent listening", lambda: session.set_agent_state("listening")),
        ("User says 'YEAH!' with punctuation", lambda: activity.on_end_of_turn("YEAH!")),
        ("User says '  yeah  ' with extra spaces", lambda: activity.on_end_of_turn("  yeah  ")),
    ]
    
    for description, action in scenarios:
        logger.info(f"\n--- {description} ---")
        action()
        await asyncio.sleep(0.5)  
    
    logger.info("\n=== Demonstration Complete ===")


if __name__ == "__main__":
    asyncio.run(simulate_conversation())