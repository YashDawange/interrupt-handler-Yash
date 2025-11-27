"""
Test agent for Backchannel Filtering: Testing intelligent interruption handling.

This agent demonstrates the backchannel filtering system that distinguishes between:
- Backchannel words (yeah, ok, hmm) that should be ignored while speaking
- Real interruptions (wait, stop) that should stop the agent immediately

Usage:
    1. Set environment variables:
       $env:OPENAI_API_KEY="your-key"
       $env:DEEPGRAM_API_KEY="your-key"
       $env:LIVEKIT_URL="wss://your-project.livekit.cloud"
       $env:LIVEKIT_API_KEY="your-key"
       $env:LIVEKIT_API_SECRET="your-secret"
    
    2. Run the agent:
       python test_interruption_agent.py dev
    
    3. Connect via agents-playground.livekit.io with generated token
    
    4. Test backchannel filtering:
       - Say "Tell me a long story about space exploration"
       - While agent speaks, say "yeah" or "hmm" → Agent continues seamlessly
       - While agent speaks, say "wait" or "stop" → Agent stops immediately
       - When agent is silent, say "yeah I understand" → Agent responds
"""

import logging
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    AgentServer,
    cli,
    InterruptionMetrics,
    MetricsCollectedEvent,
    UserInterruptedAgentEvent,
    InterruptionResumedEvent,
    tokenize,
)
from livekit.plugins import deepgram, openai, silero

# Set up logging to see interruption events
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InterruptionTestAgent(Agent):
    """Agent designed to test interruption handling."""
    
    def __init__(self):
        super().__init__(
            instructions=(
                "You are a helpful assistant. "
                "When asked to tell a story, speak in complete, flowing sentences without breaking mid-thought. "
                "Deliver your responses smoothly and continuously. "
                "Generate at least 3-4 complete sentences before pausing. "
                "If interrupted with a real command like 'stop' or 'wait', stop immediately. "
                "Ignore conversational backchannels like 'yeah', 'hmm', 'okay' - these are just acknowledgments that you should talk through. "
                "If interrupted, continue from where you left off without repeating yourself."
            ),
        )


server = AgentServer()


@server.rtc_session()
async def test_interruption_session(ctx: JobContext):
    """Session handler for testing interruptions."""
    
    logger.info("=" * 80)
    logger.info("BACKCHANNEL FILTERING TEST SESSION STARTED")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Testing Instructions:")
    logger.info("")
    logger.info("✅ TEST 1: Backchannel words (should NOT interrupt)")
    logger.info("   Say: 'Tell me a long story about space exploration'")
    logger.info("   While agent speaks, say: 'yeah' or 'hmm' or 'ok'")
    logger.info("   Expected: Agent continues speaking seamlessly")
    logger.info("")
    logger.info("✅ TEST 2: Real interruptions (should interrupt)")
    logger.info("   While agent speaks, say: 'wait' or 'stop'")
    logger.info("   Expected: Agent stops immediately")
    logger.info("")
    logger.info("✅ TEST 3: State awareness (agent silent)")
    logger.info("   When agent is NOT speaking, say: 'yeah I understand'")
    logger.info("   Expected: Agent responds to your input")
    logger.info("")
    logger.info("=" * 80)
    
    # Track interruption statistics
    interruption_count = 0
    false_interruption_count = 0
    total_pause_duration = 0.0
    
    # Create session with backchannel filtering enabled
    session = AgentSession[None](
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model="gpt-4o-mini"),
        # OpenAI TTS - reliable and uses existing OpenAI API key
        tts=openai.TTS(voice="alloy"),
        
        # Backchannel filtering configuration (CRITICAL!)
        # These words will be ignored when agent is speaking
        backchannel_ignore_words={
            # Affirmations
            'yeah', 'yep', 'yes', 'yup', 'ya', 'aye',
            # Acknowledgments  
            'ok', 'okay', 'k',
            # Thinking/filler sounds
            'hmm', 'hm', 'mhmm', 'mm', 'mmm', 'mm-hmm', 'mmhmm',
            'uh-huh', 'uhuh', 'huh',
            # Agreement words
            'right', 'alright', 'gotcha',
            # Casual acknowledgments
            'sure', 'cool', 'nice', 'great', 'good', 'fine',
            'true', 'correct', 'exactly', 'absolutely',
            'definitely', 'totally', 'certainly', 'indeed',
            # Filler sounds
            'ah', 'oh', 'uh', 'um', 'er',
            # Reactions
            'wow', 'really', 'seriously', 'interesting',
        },
        
        # Interruption configuration
        min_interruption_duration=0.3,   # Low threshold - let VAD catch short utterances, filter handles backchannel
        min_interruption_words=0,        # Set to 0 to rely on backchannel filter
        resume_false_interruption=True,  # Auto-resume on false interruptions
        false_interruption_timeout=2.0,  # Wait 2s before resuming
    )
    
    # Listen for interruption events
    @session.on("user_interrupted_agent")
    def on_interrupted(event: UserInterruptedAgentEvent):
        nonlocal interruption_count
        interruption_count += 1
        
        logger.info("")
        logger.info("🛑 " + "=" * 70)
        logger.info(f"🛑 INTERRUPTION #{interruption_count} DETECTED!")
        logger.info("🛑 " + "=" * 70)
        logger.info(f"   Speech ID: {event.speech_id}")
        logger.info(f"   Reason: {event.interruption_reason}")
        logger.info(f"   User spoke for: {event.user_speech_duration:.2f}s")
        logger.info(f"   Agent had said: '{event.partial_text}'")
        logger.info(f"   Position: {event.interruption_position:.2f}s")
        logger.info("🛑 " + "=" * 70)
        logger.info("")
    
    @session.on("interruption_resumed")
    def on_resumed(event: InterruptionResumedEvent):
        nonlocal false_interruption_count, total_pause_duration
        
        if event.was_false_interruption:
            false_interruption_count += 1
            total_pause_duration += event.pause_duration
            
            logger.info("")
            logger.info("▶️  " + "=" * 70)
            logger.info(f"▶️  FALSE INTERRUPTION RECOVERED #{false_interruption_count}")
            logger.info("▶️  " + "=" * 70)
            logger.info(f"   Speech ID: {event.speech_id}")
            logger.info(f"   Was paused for: {event.pause_duration:.2f}s")
            logger.info(f"   Agent resumed speaking automatically")
            logger.info("▶️  " + "=" * 70)
            logger.info("")
    
    @session.on("metrics_collected")
    def on_metrics(event: MetricsCollectedEvent):
        if isinstance(event.metrics, InterruptionMetrics):
            m = event.metrics
            logger.info("")
            logger.info("📊 " + "=" * 70)
            logger.info("📊 INTERRUPTION METRICS COLLECTED")
            logger.info("📊 " + "=" * 70)
            logger.info(f"   Timestamp: {m.timestamp}")
            logger.info(f"   Duration: {m.interruption_duration:.2f}s")
            logger.info(f"   False interruption: {m.was_false_interruption}")
            logger.info(f"   Partial text length: {m.partial_text_length} chars")
            logger.info(f"   Total text length: {m.total_text_length} chars")
            logger.info(f"   Interruption reason: {m.interruption_reason}")
            logger.info(f"   User speech duration: {m.user_speech_duration:.2f}s")
            logger.info("📊 " + "=" * 70)
            logger.info("")
    
    # Start the session
    await session.start(agent=InterruptionTestAgent(), room=ctx.room)
    
    # Log final statistics when session ends
    logger.info("")
    logger.info("=" * 80)
    logger.info("SESSION ENDED - FINAL STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Total interruptions: {interruption_count}")
    logger.info(f"False interruptions recovered: {false_interruption_count}")
    if false_interruption_count > 0:
        logger.info(f"Average pause duration: {total_pause_duration / false_interruption_count:.2f}s")
    logger.info("=" * 80)


if __name__ == "__main__":
    cli.run_app(server)
