"""
LiveKit Voice Agent Event Loop Integration - Complete Example

This shows exactly where and how to hook the interruption handler
into your LiveKit agent's event loop.
"""

import asyncio
import time
import logging
from typing import Optional, Callable, Any

from livekit.agents.voice.interruption_handler import (
    AgentStateManager,
    InterruptionFilter,
    load_config,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# CORE INTEGRATION CLASS
# =============================================================================


class VoiceAgentWithInterruptionHandling:
    """
    Complete integration of interruption handler into LiveKit voice agent.
    
    This class shows all the integration points and how to hook events.
    """
    
    def __init__(self, agent: Optional[Any] = None):
        """Initialize agent with intelligent interruption handling."""
        self.agent = agent
        
        # ─────────────────────────────────────────────────────────────
        # STEP 1: Initialize Interruption Handler Components
        # ─────────────────────────────────────────────────────────────
        self.config = load_config()
        self.state_manager = AgentStateManager()
        self.interrupt_filter = InterruptionFilter(
            ignore_words=self.config.ignore_words,
            command_words=self.config.command_words,
            enable_fuzzy_match=self.config.fuzzy_matching_enabled,
            fuzzy_threshold=self.config.fuzzy_threshold,
        )
        
        self.current_utterance_id: Optional[str] = None
        
        logger.info("✅ Interruption handler initialized")
        logger.info(
            f"  - Ignore words: {len(self.config.ignore_words)} "
            f"({', '.join(self.config.ignore_words[:3])}...)"
        )
        logger.info(
            f"  - Command words: {len(self.config.command_words)} "
            f"({', '.join(self.config.command_words[:3])}...)"
        )
    
    # ─────────────────────────────────────────────────────────────────
    # INTEGRATION POINT 1: When Agent Starts Speaking
    # ─────────────────────────────────────────────────────────────────
    
    async def on_agent_start_speaking(self, utterance) -> None:
        """
        Hook into agent's TTS start event.
        
        In your LiveKit agent:
            - This is called when agent's speech synthesis starts
            - Could be from LLM response, pre-recorded prompt, etc.
        
        In your code, hook it like:
            agent.on_tts_start += self.on_agent_start_speaking
        """
        self.current_utterance_id = f"utt_{time.time()}"
        await self.state_manager.start_speaking(self.current_utterance_id)
        logger.debug(f"🔊 Agent START speaking: {self.current_utterance_id}")
    
    # ─────────────────────────────────────────────────────────────────
    # INTEGRATION POINT 2: When Agent Stops Speaking
    # ─────────────────────────────────────────────────────────────────
    
    async def on_agent_stop_speaking(self) -> None:
        """
        Hook into agent's TTS end event.
        
        In your LiveKit agent:
            - This is called when agent's speech synthesis ends
            - Could be normal completion or interruption
        
        In your code, hook it like:
            agent.on_tts_end += self.on_agent_stop_speaking
        """
        await self.state_manager.stop_speaking()
        logger.debug("🔇 Agent STOP speaking")
    
    # ─────────────────────────────────────────────────────────────────
    # INTEGRATION POINT 3: When User Speech Detected (VAD)
    # ─────────────────────────────────────────────────────────────────
    
    async def on_vad_event(
        self,
        vad_event,
        get_stt_transcription_coro,
    ) -> bool:
        """
        Hook into VAD (Voice Activity Detection) event.
        
        This is THE CRITICAL INTEGRATION POINT for interruption handling.
        
        In your LiveKit agent:
            - VAD fires when user speech is detected
            - This happens IMMEDIATELY (< 50ms)
            - But STT takes 200-500ms to transcribe
            - We wait for STT to know WHAT the user said
        
        In your code, hook it like:
            agent.on_vad_event += self.on_vad_event
        
        Parameters:
            vad_event: The VAD event from LiveKit
            get_stt_transcription_coro: Async function that returns STT text
        
        Returns:
            True: Interrupt the agent
            False: Continue agent speaking, ignore user input
        """
        logger.debug("🎤 VAD EVENT detected")
        
        # Get current agent state - non-blocking operation (< 1ms)
        agent_state = self.state_manager.get_state()
        
        # ─────────────────────────────────────────────────────────────
        # Decision 1: Is agent currently speaking?
        # ─────────────────────────────────────────────────────────────
        if not agent_state.is_speaking:
            logger.debug("   Agent not speaking → Normal VAD behavior")
            return False  # Let LiveKit handle it normally
        
        logger.debug(f"   Agent IS speaking (for {agent_state.speech_duration:.2f}s)")
        
        # ─────────────────────────────────────────────────────────────
        # Decision 2: Wait for STT transcription
        # ─────────────────────────────────────────────────────────────
        try:
            # Convert timeout from ms to seconds
            timeout_sec = self.config.stt_wait_timeout_ms / 1000.0
            
            logger.debug(f"   Waiting for STT (timeout: {timeout_sec}s)...")
            text = await asyncio.wait_for(
                get_stt_transcription_coro,
                timeout=timeout_sec
            )
            logger.debug(f"   STT received: '{text}'")
            
        except asyncio.TimeoutError:
            logger.warning(
                f"   ⏱️  STT TIMEOUT after {self.config.stt_wait_timeout_ms}ms"
            )
            logger.warning("   → Defaulting to INTERRUPT (safe)")
            return True  # Safe default: interrupt if STT is too slow
        
        except Exception as e:
            logger.error(f"   ❌ STT ERROR: {e}")
            logger.warning("   → Defaulting to INTERRUPT (safe)")
            return True  # Safe default: interrupt on error
        
        if not text or not text.strip():
            logger.debug("   Empty transcription → IGNORE")
            return False
        
        # ─────────────────────────────────────────────────────────────
        # Decision 3: Make interruption decision using filter
        # ─────────────────────────────────────────────────────────────
        decision = self.interrupt_filter.should_interrupt_detailed(
            text,
            agent_state.to_dict()
        )
        
        # Log decision
        action = "🛑 INTERRUPT" if decision.should_interrupt else "✅ IGNORE"
        logger.info(
            f"   {action}: '{text}' ({decision.classified_as})"
        )
        if self.config.log_all_decisions:
            logger.info(f"   Reason: {decision.reason}")
        
        return decision.should_interrupt
    
    # ─────────────────────────────────────────────────────────────────
    # Utility: Get current state for debugging
    # ─────────────────────────────────────────────────────────────────
    
    def get_current_state(self):
        """Get current agent state - useful for debugging."""
        state = self.state_manager.get_state()
        return {
            "is_speaking": state.is_speaking,
            "utterance_id": state.utterance_id,
            "speech_duration_seconds": state.speech_duration,
        }


# =============================================================================
# EXAMPLE: Hooking into Your LiveKit Agent
# =============================================================================


async def setup_agent_with_interruption_handling(
    agent: Optional[Any] = None,
) -> VoiceAgentWithInterruptionHandling:
    """
    Setup your existing LiveKit agent with interruption handling.
    
    Example usage:
        async def main():
            agent = agents.VoiceAssistant(...)
            
            # Setup interruption handling
            handler = await setup_agent_with_interruption_handling(agent)
            
            # Now your agent has intelligent interruption handling!
    """
    handler = VoiceAgentWithInterruptionHandling(agent)
    return handler


# =============================================================================
# EXAMPLE: Minimal Integration (Just the essentials)
# =============================================================================


async def minimal_integration_example():
    """
    Minimal example showing just the core interruption logic.
    
    Copy this pattern into your own agent code.
    """
    from livekit.agents.voice.interruption_handler import (
        AgentStateManager,
        InterruptionFilter,
        load_config,
    )
    
    # 1. Initialize components
    config = load_config()
    state_mgr = AgentStateManager()
    filter = InterruptionFilter(
        ignore_words=config.ignore_words,
        command_words=config.command_words,
    )
    
    # 2. When agent speaks
    await state_mgr.start_speaking("utterance_123")
    
    # 3. When VAD detects user speech
    async def handle_vad():
        state = state_mgr.get_state()
        
        if not state.is_speaking:
            return False
        
        # Get STT transcription
        try:
            text = await asyncio.wait_for(stt_service.transcribe(), timeout=0.5)
        except:
            return True  # Interrupt on timeout
        
        # Decide
        should_interrupt, _ = filter.should_interrupt(text, state.to_dict())
        return should_interrupt
    
    # 4. When agent stops
    await state_mgr.stop_speaking()


# =============================================================================
# EXAMPLE: Event Loop Patterns
# =============================================================================


class LiveKitEventIntegration:
    """Different ways to integrate with LiveKit's event loop."""
    
    @staticmethod
    async def pattern_1_event_handlers(agent, handler):
        """Pattern 1: Register event handlers."""
        # For each event type, call the appropriate handler
        
        # When agent starts speaking (adjust based on your actual agent API)
        # @agent.on_event(agents_pb2.SessionEvent.Kind.AGENT_SPEECH_STARTED)
        # async def _(event):
        #     await handler.on_agent_start_speaking(event)
        
        # When user speech detected
        # @agent.on_event(agents_pb2.SessionEvent.Kind.USER_SPEECH_DETECTED)
        # async def _(event):
        #     return await handler.on_vad_event(
        #         event,
        #         agent.stt.transcribe(event)
        #     )
        
        logger.info("Pattern 1: Event handler style integration")
    
    @staticmethod
    async def pattern_2_callback_style(agent, handler):
        """Pattern 2: Register callbacks."""
        # These methods are pseudo-code and depend on your actual agent API
        # agent.on_agent_start_speaking += handler.on_agent_start_speaking
        # agent.on_agent_stop_speaking += handler.on_agent_stop_speaking
        # agent.on_vad_event += handler.on_vad_event
        
        logger.info("Pattern 2: Callback style integration")
    
    @staticmethod
    async def pattern_3_middleware(agent, handler):
        """Pattern 3: Wrap VAD handler as middleware."""
        # This is pseudo-code - adjust based on your actual agent API
        # original_vad_handler = agent.handle_vad
        
        # async def wrapped_vad_handler(vad_event):
        #     # Try intelligent interruption first
        #     result = await handler.on_vad_event(
        #         vad_event,
        #         agent.stt.transcribe(vad_event)
        #     )
        #
        #     if result is not None:
        #         return result  # Use our decision
        #     else:
        #         return await original_vad_handler(vad_event)  # Fall back
        #
        # agent.handle_vad = wrapped_vad_handler
        
        logger.info("Pattern 3: Middleware style integration")


# =============================================================================
# EXAMPLE: Testing Your Integration
# =============================================================================


async def test_integration_locally():
    """Test the integration without connecting to LiveKit."""
    logger.info("Testing interruption handler integration...")
    
    # Create minimal mock agent
    class MockAgent:
        pass
    
    agent = MockAgent()
    handler = VoiceAgentWithInterruptionHandling(agent)
    
    # Simulate agent speaking
    await handler.on_agent_start_speaking(None)
    logger.info(f"State: {handler.get_current_state()}")
    
    # Simulate VAD event with "yeah"
    async def mock_stt_yeah():
        await asyncio.sleep(0.1)
        return "yeah"
    
    should_interrupt = await handler.on_vad_event(None, mock_stt_yeah())
    assert not should_interrupt, "Should NOT interrupt on backchannel"
    logger.info("✅ Backchannel test passed")
    
    # Simulate VAD event with "stop"
    async def mock_stt_stop():
        await asyncio.sleep(0.1)
        return "stop"
    
    should_interrupt = await handler.on_vad_event(None, mock_stt_stop())
    assert should_interrupt, "Should interrupt on command"
    logger.info("✅ Command test passed")
    
    # Simulate agent stop
    await handler.on_agent_stop_speaking()
    logger.info(f"Final state: {handler.get_current_state()}")
    
    logger.info("✅ All integration tests passed!")


if __name__ == "__main__":
    asyncio.run(test_integration_locally())
