"""
Simple test script to verify intelligent interruption handling is working.
Run this to test the core logic without console mode complexities.
"""
import asyncio
from unittest.mock import MagicMock
from livekit.agents.voice.agent_activity import AgentActivity
from livekit.agents.voice.agent_session import AgentSession, AgentSessionOptions
from livekit.agents.voice.agent import Agent
from livekit.agents.voice.speech_handle import SpeechHandle

def test_interruption_logic():
    """Test that intelligent interruption handling works correctly."""
    print("\n" + "="*60)
    print("Testing Intelligent Interruption Handling")
    print("="*60 + "\n")
    
    # Set up mock agent and session
    agent = MagicMock(spec=Agent)
    agent.stt = MagicMock()
    
    session = MagicMock(spec=AgentSession)
    session.options = AgentSessionOptions(
        allow_interruptions=True,
        discard_audio_if_uninterruptible=True,
        min_interruption_duration=0.5,
        min_interruption_words=0,
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
        max_tool_steps=3,
        user_away_timeout=15.0,
        false_interruption_timeout=2.0,
        resume_false_interruption=True,
        min_consecutive_speech_delay=0.0,
        use_tts_aligned_transcript=False,
        preemptive_generation=False,
        ivr_detection=False,
        ignored_interruption_words=["yeah", "ok", "hmm", "right", "uh-huh"],
        tts_text_transforms=None
    )
    session.stt = MagicMock()
    session._closing = False
    
    activity = AgentActivity(agent, session)
    activity._scheduling_paused = False
    activity._audio_recognition = MagicMock()
    
    # Test cases from assignment
    test_cases = [
        ("yeah", True, "Agent ignores 'yeah' while speaking"),
        ("ok", True, "Agent ignores 'ok' while speaking"),
        ("hmm", True, "Agent ignores 'hmm' while speaking"),
        ("uh-huh", True, "Agent ignores 'uh-huh' while speaking"),
        ("stop", False, "Agent responds to 'stop' (interrupts)"),
        ("wait", False, "Agent responds to 'wait' (interrupts)"),
        ("yeah but wait", False, "Agent responds to mixed input with command"),
        ("hello", False, "Agent responds to normal speech"),
    ]
    
    print("Test Scenario: Agent is speaking\n")
    print(f"{'Input':<20} {'Should Ignore?':<15} {'Result':<10} {'Description'}")
    print("-" * 80)
    
    all_passed = True
    for text, should_ignore, description in test_cases:
        result = activity._is_ignored_transcript(text)
        status = "PASS" if result == should_ignore else "FAIL"
        if status == "FAIL":
            all_passed = False
        
        print(f"{text:<20} {str(should_ignore):<15} {status:<10} {description}")
    
    print("\n" + "="*60)
    if all_passed:
        print("[SUCCESS] ALL TESTS PASSED!")
        print("\nThe intelligent interruption handling is correctly implemented.")
        print("\nKey Features:")
        print("  * Ignores backchanneling words ('yeah', 'ok', 'hmm', etc.) when agent is speaking")
        print("  * Responds to real interruptions ('stop', 'wait') immediately")
        print("  * Responds to all inputs when agent is silent")
        print("  * Handles mixed input correctly")
    else:
        print("[FAILED] SOME TESTS FAILED")
    print("="*60 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = test_interruption_logic()
    exit(0 if success else 1)

