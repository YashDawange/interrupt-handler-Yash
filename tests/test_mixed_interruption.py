from __future__ import annotations
import asyncio
import pytest
from livekit.agents import Agent, ConversationItemAddedEvent
from .fake_session import FakeActions, create_session, run_session

class MyAgent(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful assistant.")
    
    async def on_enter(self):
        await self.session.say("I am speaking a very long sentence.")

async def test_mixed_input_interruption():
    """Test that mixed input like 'Yeah okay but wait' triggers interruption"""
    speed = 5.0
    actions = FakeActions()
    
    # Agent speaks
    actions.add_llm("I am speaking a very long sentence.", duration=0.1, input="User said something")
    actions.add_tts(5.0, duration=0.1)
    
    # User says "Yeah okay but wait" which contains non-ignored word
    actions.add_user_speech(1.0, 0.5, "Yeah okay but wait", stt_delay=0.1)
    
    session = create_session(actions, speed_factor=speed, extra_kwargs={"ignored_words": ["yeah", "okay"]})
    agent = MyAgent()
    
    conversation_events = []
    session.on("conversation_item_added", conversation_events.append)
    
    await run_session(session, agent)
    
    # Verify the mixed input WAS added to conversation (because it contains "but wait")
    messages = [c for e in conversation_events if e.item.role == "user" for c in e.item.content]
    assert "Yeah okay but wait" in messages, "Mixed input should be added because it contains non-ignored words"

async def test_all_ignored_words():
    """Test that input with only ignored words is completely ignored"""
    speed = 5.0
    actions = FakeActions()
    
    # Agent speaks
    actions.add_llm("I am speaking a very long sentence.", duration=0.1, input="User said something")
    actions.add_tts(5.0, duration=0.1)
    
    # User says "Yeah okay hmm" which are all ignored words
    actions.add_user_speech(1.0, 0.5, "Yeah okay hmm", stt_delay=0.1)
    
    session = create_session(actions, speed_factor=speed, extra_kwargs={"ignored_words": ["yeah", "okay", "hmm"]})
    agent = MyAgent()
    
    conversation_events = []
    session.on("conversation_item_added", conversation_events.append)
    
    await run_session(session, agent)
    
    # Verify the input was NOT added to conversation
    messages = [c for e in conversation_events if e.item.role == "user" for c in e.item.content]
    assert "Yeah okay hmm" not in messages, "All ignored words should be ignored"