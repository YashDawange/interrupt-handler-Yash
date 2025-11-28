from __future__ import annotations

import asyncio
import pytest

from livekit.agents import (
    Agent,
    AgentStateChangedEvent,
    function_tool,
)
from livekit.agents.llm import FunctionToolCall
from livekit.agents.llm.chat_context import ChatContext, ChatMessage
from livekit.agents.voice.io import PlaybackFinishedEvent

from .fake_session import FakeActions, create_session, run_session

class MyAgent(Agent):
    def __init__(
        self,
        *,
        ignored_words: list[str] | None = None,
    ) -> None:
        super().__init__(
            instructions=("You are a helpful assistant."),
            ignored_words=ignored_words,
        )

    async def on_enter(self) -> None:
        pass

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage) -> None:
        pass

SESSION_TIMEOUT = 60.0

def check_timestamp(
    t_event: float, t_target: float, *, speed_factor: float = 1.0, max_abs_diff: float = 0.5
) -> None:
    t_event = t_event * speed_factor
    assert abs(t_event - t_target) <= max_abs_diff, (
        f"event timestamp {t_event} is not within {max_abs_diff} of target {t_target}"
    )

async def test_ignored_words_interruption() -> None:
    speed = 5.0
    actions = FakeActions()
    actions.add_user_speech(0.5, 2.5, "Tell me a story.")
    actions.add_llm("Here is a long story for you ... the end.")
    actions.add_tts(10.0)  # playout starts at 3.5s
    
    # "yeah" at 5.0s (during TTS). Should be IGNORED.
    actions.add_user_speech(5.0, 5.5, "yeah", stt_delay=0.2)
    
    # "stop" at 8.0s (during TTS). Should INTERRUPT.
    actions.add_user_speech(8.0, 8.5, "stop", stt_delay=0.2)

    session = create_session(
        actions,
        speed_factor=speed,
        extra_kwargs={"ignored_words": ["yeah", "ok"]},
    )
    agent = MyAgent(ignored_words=["yeah", "ok"])

    agent_state_events: list[AgentStateChangedEvent] = []
    playback_finished_events: list[PlaybackFinishedEvent] = []
    session.on("agent_state_changed", agent_state_events.append)
    session.output.audio.on("playback_finished", playback_finished_events.append)

    t_origin = await asyncio.wait_for(run_session(session, agent), timeout=SESSION_TIMEOUT)

    # Verify events
    # We expect the agent to START speaking, ignore "yeah", and then stop at "stop".
    
    # Check playback finished events
    # The first playback (the story) should be interrupted eventually, but NOT by "yeah".
    assert len(playback_finished_events) == 1
    assert playback_finished_events[0].interrupted is True
    
    # "yeah" ends at 5.5s + 0.2s delay = 5.7s. 
    # "stop" ends at 8.5s + 0.2s delay = 8.7s.
    # Playback started at 3.5s.
    # If "yeah" interrupted, playback duration would be ~2.2s (5.7 - 3.5).
    # If "stop" interrupted, playback duration would be ~5.2s (8.7 - 3.5).
    
    # Let's check the playback position.
    # 8.7s (interruption time) - 3.5s (start time) = 5.2s
    check_timestamp(playback_finished_events[0].playback_position, 5.2, speed_factor=speed, max_abs_diff=0.5)

    # Check agent state changes
    # listening -> thinking -> speaking -> (ignore yeah) -> listening (at stop) -> thinking
    
    states = [e.new_state for e in agent_state_events]
    print(states)
    
    # 0: listening (initial)
    # 1: thinking (after "Tell me a story")
    # 2: speaking (start story)
    # 3: listening (after "stop")
    # 4: thinking (processing "stop")
    # 5: listening (done)
    
    assert "speaking" in states
    
    # Ensure we didn't go back to listening/thinking around the "yeah" time (5.7s)
    # The "speaking" state should persist until ~8.7s
    
    speaking_event = next(e for e in agent_state_events if e.new_state == "speaking")
    next_event = next(e for e in agent_state_events if e.created_at > speaking_event.created_at)
    
    # The next event should be the interruption by "stop"
    check_timestamp(next_event.created_at - t_origin, 8.7, speed_factor=speed, max_abs_diff=0.5)

async def test_ignored_words_false_start_logic() -> None:
    # Test that we wait for STT if we have ignored words, effectively handling false starts
    # If we didn't wait, VAD would interrupt immediately at 5.0s.
    # Since "yeah" is ignored, we shouldn't interrupt at all.
    
    speed = 5.0
    actions = FakeActions()
    actions.add_user_speech(0.5, 2.5, "Tell me a story.")
    actions.add_llm("Here is a long story for you ... the end.")
    actions.add_tts(10.0)  # playout starts at 3.5s
    
    # "yeah" at 5.0s. VAD triggers here. STT comes at 5.7s.
    actions.add_user_speech(5.0, 5.5, "yeah", stt_delay=0.2)

    session = create_session(
        actions,
        speed_factor=speed,
        extra_kwargs={"ignored_words": ["yeah"]},
    )
    agent = MyAgent(ignored_words=["yeah"])

    playback_finished_events: list[PlaybackFinishedEvent] = []
    session.output.audio.on("playback_finished", playback_finished_events.append)

    await asyncio.wait_for(run_session(session, agent), timeout=SESSION_TIMEOUT)

    # Should NOT be interrupted
    assert len(playback_finished_events) == 1
    assert playback_finished_events[0].interrupted is False
    check_timestamp(playback_finished_events[0].playback_position, 10.0, speed_factor=speed)
