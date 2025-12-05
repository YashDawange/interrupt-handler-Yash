from __future__ import annotations
import asyncio
import pytest
from livekit.agents import Agent, AgentStateChangedEvent, ConversationItemAddedEvent
from .fake_session import FakeActions, create_session, run_session

class MyAgent(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful assistant.")
    
    async def on_enter(self):
        await self.session.say("I am speaking a very long sentence.")

async def test_ignored_interruption():
    speed = 5.0
    actions = FakeActions()
    
    # Agent speaks
    actions.add_llm("I am speaking a very long sentence.", duration=0.1, input="User said something")
    actions.add_tts(5.0, duration=0.1) # 5s audio
    
    # User says "Yeah" at 1.0s
    actions.add_user_speech(1.0, 0.5, "Yeah", stt_delay=0.1)
    
    session = create_session(actions, speed_factor=speed, extra_kwargs={"ignored_words": ["yeah"]})
    agent = MyAgent()
    
    conversation_events = []
    session.on("conversation_item_added", conversation_events.append)
    
    await run_session(session, agent)
    
    # Verify "Yeah" was NOT added to conversation
    messages = [c for e in conversation_events if e.item.role == "user" for c in e.item.content]
    assert "Yeah" not in messages, "Ignored word 'Yeah' should not be added to conversation"

async def test_valid_interruption():
    speed = 5.0
    actions = FakeActions()
    
    actions.add_llm("I am speaking a very long sentence.", duration=0.1, input="User said something")
    actions.add_tts(5.0, duration=0.1)
    
    actions.add_user_speech(1.0, 0.5, "Stop", stt_delay=0.1)
    
    session = create_session(actions, speed_factor=speed, extra_kwargs={"ignored_words": ["yeah"]})
    agent = MyAgent()
    
    conversation_events = []
    session.on("conversation_item_added", conversation_events.append)
    
    await run_session(session, agent)
    
    # Verify "Stop" WAS added to conversation
    messages = [c for e in conversation_events if e.item.role == "user" for c in e.item.content]
    assert "Stop" in messages, "Valid interruption 'Stop' should be added to conversation"

async def test_silent_response():
    speed = 5.0
    actions = FakeActions()
    
    # Agent is silent initially (we don't trigger say on enter)
    # User says "Yeah"
    actions.add_user_speech(1.0, 0.5, "Yeah", stt_delay=0.1)
    
    session = create_session(actions, speed_factor=speed, extra_kwargs={"ignored_words": ["yeah"]})
    agent = Agent(instructions="You are a helpful assistant.") # Default agent, no on_enter speech
    
    conversation_events = []
    session.on("conversation_item_added", conversation_events.append)
    
    await run_session(session, agent)
    
    # Verify "Yeah" WAS added to conversation
    messages = [c for e in conversation_events if e.item.role == "user" for c in e.item.content]
    assert "Yeah" in messages, "Word 'Yeah' should be accepted when agent is silent"