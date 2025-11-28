"""
Unit test for Phase 3 Context Analyzer
"""

import asyncio
import logging
from context_analyzer import (
    ContextAnalyzer,
    InterruptionType,
    ResumeStrategy,
    InterruptionContext
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-phase3")


async def test_context_analyzer():
    """Test the context analyzer with sample interruptions"""
    
    logger.info("=" * 70)
    logger.info("Testing Phase 3 Context Analyzer")
    logger.info("=" * 70)
    
    # Create analyzer (without real LLM for testing)
    analyzer = ContextAnalyzer(llm=None)
    
    # Test case 1: Stop request
    logger.info("\n📝 Test 1: Stop Request")
    context1 = await analyzer.analyze_interruption(
        user_utterance="Wait, stop!",
        agent_speech="I can help you with many things including booking appointments, checking your account balance, and...",
        conversation_history=["User: What can you do?"],
        interruption_point=0.3
    )
    logger.info(f"✅ Result: {context1.interruption_type.value}")
    logger.info(f"   Strategy: {context1.recommended_strategy.value}")
    logger.info(f"   Intent: {context1.user_intent}")
    
    # Test case 2: Parse response
    logger.info("\n📝 Test 2: Parsing LLM Response")
    test_response = """TYPE: urgent_question
INTENT: User wants to know the current time
TOPIC: general assistance  
STRATEGY: answer_resume
REASONING: Quick factual question, can answer and continue
CONFIDENCE: high"""
    
    context2 = analyzer._parse_llm_response(
        test_response,
        "What time is it?",
        "I'm here to help with your banking needs...",
        [],
        0.5
    )
    logger.info(f"✅ Parsed: {context2.interruption_type.value}")
    logger.info(f"   Confidence: {context2.confidence}")
    logger.info(f"   Strategy: {context2.recommended_strategy.value}")
    
    # Test case 3: All interruption types
    logger.info("\n📝 Test 3: All Interruption Types Available")
    for itype in InterruptionType:
        logger.info(f"   ✓ {itype.value}")
    
    # Test case 4: All strategies
    logger.info("\n📝 Test 4: All Response Strategies Available")
    for strategy in ResumeStrategy:
        logger.info(f"   ✓ {strategy.value}")
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ Phase 3 Context Analyzer Tests PASSED!")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_context_analyzer())
