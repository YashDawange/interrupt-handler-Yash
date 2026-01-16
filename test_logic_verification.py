"""
Quick logic verification for Intelligent Interruption Handling.
This tests the core decision logic without requiring full LiveKit setup.
"""

import asyncio
import sys
import os

# Add the module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "livekit-agents"))

from livekit.agents.voice.interruption_handler import InterruptionHandler


async def test_scenario_1_long_explanation():
    """Scenario 1: Agent speaking + fillers → IGNORE"""
    print("\n" + "=" * 60)
    print("TEST 1: Long Explanation (Agent speaking + 'yeah')")
    print("=" * 60)
    
    handler = InterruptionHandler()
    handler.set_agent_speaking(True)
    
    # User says "yeah" while agent is speaking
    vad_decision = await handler.on_vad_event()
    print(f"VAD Event: {vad_decision.reason}")
    assert vad_decision.is_pending, "Should be pending"
    assert not vad_decision.should_interrupt, "Should not interrupt yet"
    
    # STT produces "yeah"
    stt_decision = await handler.on_stt_result("yeah")
    print(f"STT Result 'yeah': {stt_decision.reason}")
    assert not stt_decision.should_interrupt, "FAIL: Agent should continue speaking!"
    
    print("✅ PASS: Agent continues speaking over 'yeah'")
    return True


async def test_scenario_2_passive_affirmation():
    """Scenario 2: Agent silent + 'yeah' → RESPOND"""
    print("\n" + "=" * 60)
    print("TEST 2: Passive Affirmation (Agent silent + 'yeah')")
    print("=" * 60)
    
    handler = InterruptionHandler()
    handler.set_agent_speaking(False)  # Agent is SILENT
    
    # User says "yeah" when agent is silent
    vad_decision = await handler.on_vad_event()
    print(f"VAD Event: {vad_decision.reason}")
    assert not vad_decision.is_pending, "Should not be pending"
    assert vad_decision.should_interrupt, "Should allow normal processing"
    
    print("✅ PASS: Agent will process 'yeah' as normal input")
    return True


async def test_scenario_3_correction():
    """Scenario 3: Agent speaking + 'stop' → INTERRUPT"""
    print("\n" + "=" * 60)
    print("TEST 3: Correction (Agent speaking + 'stop')")
    print("=" * 60)
    
    handler = InterruptionHandler()
    handler.set_agent_speaking(True)
    
    # User says "stop" while agent is speaking
    vad_decision = await handler.on_vad_event()
    print(f"VAD Event: {vad_decision.reason}")
    
    # STT produces "stop"
    stt_decision = await handler.on_stt_result("stop")
    print(f"STT Result 'stop': {stt_decision.reason}")
    assert stt_decision.should_interrupt, "FAIL: Should interrupt on command!"
    
    print("✅ PASS: Agent stops on command word")
    return True


async def test_scenario_4_mixed_input():
    """Scenario 4: Agent speaking + 'yeah but wait' → INTERRUPT"""
    print("\n" + "=" * 60)
    print("TEST 4: Mixed Input (Agent speaking + 'yeah but wait')")
    print("=" * 60)
    
    handler = InterruptionHandler()
    handler.set_agent_speaking(True)
    
    # User says mixed input
    await handler.on_vad_event()
    
    # STT produces "yeah but wait"
    stt_decision = await handler.on_stt_result("yeah but wait")
    print(f"STT Result 'yeah but wait': {stt_decision.reason}")
    assert stt_decision.should_interrupt, "FAIL: Should interrupt on mixed input with command!"
    
    print("✅ PASS: Agent stops on mixed input containing command")
    return True


async def test_edge_cases():
    """Additional edge case tests"""
    print("\n" + "=" * 60)
    print("EDGE CASES")
    print("=" * 60)
    
    handler = InterruptionHandler()
    handler.set_agent_speaking(True)
    
    # Test 1: Multiple fillers
    await handler.on_vad_event()
    decision = await handler.on_stt_result("yeah ok hmm")
    assert not decision.should_interrupt, "Multiple fillers should be ignored"
    print("✅ Multiple fillers ignored")
    
    # Test 2: Case insensitive
    await handler.on_vad_event()
    decision = await handler.on_stt_result("YEAH")
    assert not decision.should_interrupt, "Case insensitive filler should work"
    print("✅ Case insensitive works")
    
    # Test 3: Command with punctuation
    await handler.on_vad_event()
    decision = await handler.on_stt_result("stop!")
    assert decision.should_interrupt, "Command with punctuation should interrupt"
    print("✅ Punctuation handling works")
    
    # Test 4: Multi-word command
    await handler.on_vad_event()
    decision = await handler.on_stt_result("hold on")
    assert decision.should_interrupt, "Multi-word command should interrupt"
    print("✅ Multi-word command works")
    
    return True


async def main():
    """Run all tests"""
    print("\n" + "🎯" * 30)
    print("INTELLIGENT INTERRUPTION HANDLER - LOGIC VERIFICATION")
    print("🎯" * 30)
    
    try:
        # Run all test scenarios
        await test_scenario_1_long_explanation()
        await test_scenario_2_passive_affirmation()
        await test_scenario_3_correction()
        await test_scenario_4_mixed_input()
        await test_edge_cases()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! 🎉")
        print("=" * 60)
        print("\nThe logic is correct and meets all challenge requirements:")
        print("✅ Agent continues speaking over fillers (NO PAUSE)")
        print("✅ Agent responds to fillers when silent")
        print("✅ Agent stops on command words")
        print("✅ Agent handles mixed input correctly")
        print("\nNext steps:")
        print("1. Test with actual LiveKit setup")
        print("2. Record proof video/logs")
        print("3. Submit PR to Dark-Sys-Jenkins/agents-assignment")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
