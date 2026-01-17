"""
Example: Intelligent Interruption Handler Integration with LiveKit Agent

This example demonstrates how to integrate the interruption handler system
into a LiveKit voice agent. It shows:

1. Setting up the state manager and filter
2. Hooking into the agent event loop
3. Making context-aware interruption decisions
4. Handling the VAD-STT race condition
"""

import asyncio
import logging
from typing import Optional

from livekit.agents.voice.interruption_handler import (
    AgentStateManager,
    InterruptionFilter,
    load_config,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntelligentInterruptionHandler:
    """
    Wrapper class that integrates the interruption handler system
    with a LiveKit agent.
    
    This handles the VAD-STT synchronization and makes the final
    interruption decision.
    """
    
    def __init__(
        self,
        agent,
        config_file: Optional[str] = None,
    ):
        """
        Initialize the interruption handler.
        
        Args:
            agent: The LiveKit agent instance.
            config_file: Optional path to interruption_config.json.
        """
        self.agent = agent
        
        # Load configuration
        self.config = load_config(config_file=config_file)
        
        # Initialize components
        self.state_manager = AgentStateManager()
        self.interrupt_filter = InterruptionFilter(
            ignore_words=self.config.ignore_words,
            command_words=self.config.command_words,
            enable_fuzzy_match=self.config.fuzzy_matching_enabled,
            fuzzy_threshold=self.config.fuzzy_threshold,
        )
        
        logger.info("IntelligentInterruptionHandler initialized")
        if self.config.verbose_logging:
            logger.setLevel(logging.DEBUG)
    
    async def on_agent_start_speaking(self, utterance_id: str) -> None:
        """
        Call this when the agent starts speaking.
        
        Args:
            utterance_id: Unique identifier for this speech segment.
        """
        await self.state_manager.start_speaking(utterance_id)
        logger.debug(f"Agent started speaking: {utterance_id}")
    
    async def on_agent_stop_speaking(self) -> None:
        """Call this when the agent stops speaking."""
        await self.state_manager.stop_speaking()
        logger.debug("Agent stopped speaking")
    
    async def on_user_speech_event(
        self,
        vad_event,
        get_stt_transcription,
    ) -> Optional[bool]:
        """
        Handle user speech event with intelligent interruption decision.
        
        This is the main integration point. Call this when VAD detects
        user speech.
        
        Args:
            vad_event: The VAD event from LiveKit.
            get_stt_transcription: Async function that returns STT text
                                  for this speech event.
        
        Returns:
            True if agent should be interrupted, False to continue speaking,
            or None to use default behavior.
        
        Example:
            # In your agent's event handler:
            async def on_vad_event(vad_event):
                should_interrupt = await handler.on_user_speech_event(
                    vad_event,
                    lambda: get_transcription_for_event(vad_event)
                )
                
                if should_interrupt:
                    await agent.stop_speaking()
                    # Process user input
                elif should_interrupt is False:
                    # Continue speaking, ignore the input
                    pass
        """
        if not self.config.enabled:
            return None  # Use default behavior
        
        # Get current agent state
        agent_state = self.state_manager.get_state()
        
        # If agent isn't speaking, use default behavior
        if not agent_state.is_speaking:
            return None
        
        # Wait for STT transcription
        try:
            # Convert timeout from ms to seconds
            timeout_seconds = self.config.stt_wait_timeout_ms / 1000.0
            
            text = await asyncio.wait_for(
                get_stt_transcription(),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            # STT took too long, default to interrupt (safe default)
            logger.warning(
                f"STT timeout ({self.config.stt_wait_timeout_ms}ms), "
                "defaulting to interrupt"
            )
            return True
        except Exception as e:
            logger.error(f"Error getting STT transcription: {e}")
            return True  # Safe default
        
        if not text or not text.strip():
            logger.debug("Empty transcription, ignoring")
            return False  # Ignore empty transcriptions
        
        # Make interruption decision
        decision = self.interrupt_filter.should_interrupt_detailed(
            text,
            agent_state.to_dict()
        )
        
        # Log the decision if configured
        if self.config.log_all_decisions:
            logger.info(
                f"Interruption decision: {decision.should_interrupt} "
                f"({decision.classified_as}) for text: '{text}'"
            )
        else:
            logger.debug(
                f"Interruption decision: {decision.should_interrupt} "
                f"({decision.classified_as}) for text: '{text}'"
            )
        
        return decision.should_interrupt


# =============================================================================
# Example Usage
# =============================================================================


class ExampleAgent:
    """Example agent showing integration with interruption handler."""
    
    def __init__(self):
        self.handler = IntelligentInterruptionHandler(self)
        self.current_utterance_id = None
    
    async def say(self, text: str) -> None:
        """
        Example method: Agent says something.
        
        In a real agent, this would use TTS and integration with LiveKit.
        """
        # Generate unique ID for this speech
        self.current_utterance_id = f"utt_{id(self)}"
        
        # Notify interruption handler
        await self.handler.on_agent_start_speaking(self.current_utterance_id)
        
        logger.info(f"Agent saying: {text}")
        
        # Simulate speech duration
        await asyncio.sleep(2)
        
        # Notify when done
        await self.handler.on_agent_stop_speaking()
    
    async def handle_user_input(
        self,
        transcribed_text: str,
    ) -> None:
        """
        Example method: Process user input.
        
        In a real agent, this would integrate with the LLM and chat context.
        """
        logger.info(f"Processing user input: {transcribed_text}")
        # In a real agent, feed this to the LLM
    
    async def simulate_vad_event(self, user_text: str) -> None:
        """
        Simulate a VAD event and let interruption handler decide.
        
        Args:
            user_text: What the user said.
        """
        # Mock function that returns the transcribed text
        async def get_transcription():
            # In reality, this would call the STT service
            await asyncio.sleep(0.1)  # Simulate STT latency
            return user_text
        
        # Let handler decide
        should_interrupt = await self.handler.on_user_speech_event(
            vad_event=None,  # Not used in this example
            get_stt_transcription=get_transcription,
        )
        
        if should_interrupt:
            logger.info("→ Interrupting agent")
            await self.handler.on_agent_stop_speaking()
            await self.handle_user_input(user_text)
        elif should_interrupt is False:
            logger.info("→ Ignoring user input (backchannel)")
        else:
            logger.info("→ Using default behavior")


async def demo_scenario_1():
    """
    Demo Scenario 1: Long Explanation with Backchanneling
    
    Expected: Agent continues speaking despite user acknowledgments.
    """
    logger.info("\n" + "="*70)
    logger.info("SCENARIO 1: Long Explanation with Backchanneling")
    logger.info("="*70)
    
    agent = ExampleAgent()
    
    # Start agent speaking
    speaking_task = asyncio.create_task(
        agent.say("In 1492, Columbus sailed across the Atlantic Ocean...")
    )
    
    # Wait a bit for speech to start
    await asyncio.sleep(0.1)
    
    # User backchannels
    for backchannel, delay in [("okay", 0.3), ("yeah", 0.7), ("uh-huh", 1.3)]:
        await asyncio.sleep(delay)
        logger.info(f"User: '{backchannel}'")
        await agent.simulate_vad_event(backchannel)
    
    # Wait for agent to finish
    await speaking_task
    logger.info("Scenario 1 complete ✅\n")


async def demo_scenario_3():
    """
    Demo Scenario 3: Active Interruption
    
    Expected: Agent stops immediately when user says "stop".
    """
    logger.info("="*70)
    logger.info("SCENARIO 3: Active Interruption (Command)")
    logger.info("="*70)
    
    agent = ExampleAgent()
    
    # Start agent speaking
    speaking_task = asyncio.create_task(
        agent.say("One, two, three, four, five...")
    )
    
    # Wait a bit for speech to start
    await asyncio.sleep(0.1)
    
    # User interrupts
    await asyncio.sleep(0.5)
    logger.info("User: 'No stop.'")
    await agent.simulate_vad_event("No stop.")
    
    # Wait for potential agent response
    await asyncio.sleep(0.5)
    logger.info("Scenario 3 complete ✅\n")


async def demo_scenario_4():
    """
    Demo Scenario 4: Mixed Input
    
    Expected: Agent stops because "wait" is a command even with "yeah okay".
    """
    logger.info("="*70)
    logger.info("SCENARIO 4: Mixed Input (Backchannel + Command)")
    logger.info("="*70)
    
    agent = ExampleAgent()
    
    # Start agent speaking
    speaking_task = asyncio.create_task(
        agent.say("The capital of France is Paris, and it's located...")
    )
    
    # Wait a bit for speech to start
    await asyncio.sleep(0.1)
    
    # User says mixed input
    await asyncio.sleep(0.5)
    logger.info("User: 'Yeah okay but wait.'")
    await agent.simulate_vad_event("Yeah okay but wait.")
    
    # Wait for potential agent response
    await asyncio.sleep(0.5)
    logger.info("Scenario 4 complete ✅\n")


async def main():
    """Run all demo scenarios."""
    logger.info("\n" + "="*70)
    logger.info("LiveKit Intelligent Interruption Handler - Demo")
    logger.info("="*70)
    
    # Run scenarios
    await demo_scenario_1()
    await demo_scenario_3()
    await demo_scenario_4()
    
    logger.info("="*70)
    logger.info("All scenarios complete!")
    logger.info("="*70)


if __name__ == "__main__":
    asyncio.run(main())
