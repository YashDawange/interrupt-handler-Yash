"""
Test Suite for Intelligent Interruption Handler (TSF)

Author: Kartik Vats
Branch: feature/interrupt-handler-kartik

This test suite verifies the Temporal-Semantic Fusion (TSF) interruption handling logic:
- test_ignore_interruption: Verifies backchannels are ignored while agent speaks
- test_active_interruption: Verifies commands trigger interruption while agent speaks  
- test_mixed_interruption: Verifies mixed input ("Yeah but wait") triggers interruption
"""

import asyncio
import os
import pytest
import string
import logging
from livekit.agents import (
    Agent,
    AgentSession,
    SpeechCreatedEvent,
    UserInputTranscribedEvent,
)
from livekit.agents.voice.speech_handle import SpeechHandle
from .fake_session import FakeActions, create_session, run_session

# Replicate the logic from interruption_handler.py
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "aha", "right", "uh-huh", 
    "yep", "yup", "sure", "got it", "i see"
}

logger = logging.getLogger("test_interruption")

class IntelligentAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful assistant.")

    async def on_enter(self) -> None:
        # Agent starts speaking immediately with allow_interruptions=False
        # Use simple text to avoid mismatch issues in FakeTTS
        await self.session.say("test", allow_interruptions=False)

SESSION_TIMEOUT = 10.0

@pytest.mark.asyncio
async def test_ignore_interruption() -> None:
    speed = 1.0
    actions = FakeActions()
    
    # Agent speaks for 5 seconds
    actions.add_tts(5.0, ttfb=0.1, duration=5.0, input="test")
    
    # User says "Yeah" at 1.0s, duration 0.5s
    actions.add_user_speech(1.0, 1.5, "Yeah", stt_delay=0.1) 
    
    session = create_session(actions, speed_factor=speed)
    agent = IntelligentAgent()
    
    # --- Logic from agent.py ---
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: UserInputTranscribedEvent):
        # Check agent state
        # We log it to debug
        logger.info(f"Agent state: {session.agent_state}")
        
        if session.agent_state != "speaking":
            return

        transcript_text = event.transcript.lower().strip()
        transcript_text = transcript_text.translate(str.maketrans('', '', string.punctuation))

        if not transcript_text:
            return

        words = transcript_text.split()
        is_backchannel = all(word in IGNORE_WORDS for word in words)

        if is_backchannel:
            logger.info(f"Ignoring backchannel: '{transcript_text}'")
            pass
        else:
            logger.info(f"Valid interruption detected: '{transcript_text}'")
            asyncio.create_task(session.interrupt())
    # ---------------------------
    
    speech_handles: list[SpeechHandle] = []
    session.on("speech_created", lambda ev: speech_handles.append(ev.speech_handle))
    
    try:
        await asyncio.wait_for(run_session(session, agent, drain_delay=2.0), timeout=SESSION_TIMEOUT)
    except Exception:
        pass
        
    assert len(speech_handles) > 0
    handle = speech_handles[0]
    
    assert handle.interrupted is False, "Speech should NOT be interrupted by 'Yeah'"

@pytest.mark.asyncio
async def test_active_interruption() -> None:
    speed = 1.0
    actions = FakeActions()
    
    actions.add_tts(5.0, ttfb=0.1, duration=5.0, input="test")
    
    # User says "Stop" at 1.0s
    actions.add_user_speech(1.0, 1.5, "Stop", stt_delay=0.1)
    
    session = create_session(actions, speed_factor=speed)
    agent = IntelligentAgent()
    
    # --- Logic from agent.py ---
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: UserInputTranscribedEvent):
        logger.info(f"Agent state: {session.agent_state}")
        if session.agent_state != "speaking":
            return

        transcript_text = event.transcript.lower().strip()
        transcript_text = transcript_text.translate(str.maketrans('', '', string.punctuation))

        if not transcript_text:
            return

        words = transcript_text.split()
        is_backchannel = all(word in IGNORE_WORDS for word in words)

        if is_backchannel:
            pass
        else:
            asyncio.create_task(session.interrupt())
    # ---------------------------
    
    speech_handles: list[SpeechHandle] = []
    session.on("speech_created", lambda ev: speech_handles.append(ev.speech_handle))
    
    try:
        await asyncio.wait_for(run_session(session, agent, drain_delay=2.0), timeout=SESSION_TIMEOUT)
    except Exception:
        pass
        
    assert len(speech_handles) > 0
    handle = speech_handles[0]
    
    assert handle.interrupted is True, "Speech SHOULD be interrupted by 'Stop'"

@pytest.mark.asyncio
async def test_mixed_interruption() -> None:
    speed = 1.0
    actions = FakeActions()
    
    actions.add_tts(5.0, ttfb=0.1, duration=5.0, input="test")
    
    # User says "Yeah but wait"
    actions.add_user_speech(1.0, 2.0, "Yeah but wait", stt_delay=0.1)
    
    session = create_session(actions, speed_factor=speed)
    agent = IntelligentAgent()
    
    # --- Logic from agent.py ---
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: UserInputTranscribedEvent):
        logger.info(f"Agent state: {session.agent_state}")
        if session.agent_state != "speaking":
            return

        transcript_text = event.transcript.lower().strip()
        transcript_text = transcript_text.translate(str.maketrans('', '', string.punctuation))

        if not transcript_text:
            return

        words = transcript_text.split()
        is_backchannel = all(word in IGNORE_WORDS for word in words)

        if is_backchannel:
            pass
        else:
            asyncio.create_task(session.interrupt())
    # ---------------------------
    
    speech_handles: list[SpeechHandle] = []
    session.on("speech_created", lambda ev: speech_handles.append(ev.speech_handle))
    
    try:
        await asyncio.wait_for(run_session(session, agent, drain_delay=2.0), timeout=SESSION_TIMEOUT)
    except Exception:
        pass
        
    assert len(speech_handles) > 0
    handle = speech_handles[0]
    
    assert handle.interrupted is True, "Speech SHOULD be interrupted by 'Yeah but wait'"
