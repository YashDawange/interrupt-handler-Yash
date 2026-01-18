from __future__ import annotations

import asyncio

import pytest
import sys
from pathlib import Path

from livekit.agents import Agent, AgentStateChangedEvent
from livekit.agents.llm.chat_context import ChatContext, ChatMessage
from livekit.agents.voice.io import PlaybackFinishedEvent

tests_dir = Path(__file__).resolve().parent
sys.path.append(str(tests_dir))
from fake_session import FakeActions, create_session, run_session  # noqa: E402


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful assistant.")

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage) -> None:
        pass


SESSION_TIMEOUT = 60.0


def _find_first_state_after(
    events: list[AgentStateChangedEvent], *, state: str, after_state: str
) -> float | None:
    seen_after = False
    for ev in events:
        if ev.new_state == after_state:
            seen_after = True
            continue
        if seen_after and ev.new_state == state:
            return ev.created_at
    return None


@pytest.mark.asyncio
async def test_agent_speaking_backchannel_continues() -> None:
    actions = FakeActions()
    actions.add_user_speech(0.5, 2.5, "Tell me a story.")
    actions.add_llm("Here is a long story for you...", ttft=0.1, duration=0.3)
    actions.add_tts(6.0)
    actions.add_user_speech(3.0, 3.6, "okay yeah uh-huh", stt_delay=0.1)

    session = create_session(actions, speed_factor=5.0)
    agent = MyAgent()

    playback_finished_events: list[PlaybackFinishedEvent] = []
    session.output.audio.on("playback_finished", playback_finished_events.append)

    await asyncio.wait_for(run_session(session, agent), timeout=SESSION_TIMEOUT)

    assert len(playback_finished_events) == 1
    assert playback_finished_events[0].interrupted is False


@pytest.mark.asyncio
async def test_agent_silent_user_speaks_is_valid_input() -> None:
    actions = FakeActions()
    actions.add_user_speech(0.5, 1.0, "yeah", stt_delay=0.1)
    actions.add_llm("Okay.", ttft=0.1, duration=0.2)
    actions.add_tts(1.0)

    session = create_session(actions, speed_factor=5.0)
    agent = MyAgent()

    playback_finished_events: list[PlaybackFinishedEvent] = []
    session.output.audio.on("playback_finished", playback_finished_events.append)

    await asyncio.wait_for(run_session(session, agent), timeout=SESSION_TIMEOUT)

    assert len(playback_finished_events) == 1
    assert playback_finished_events[0].interrupted is False


@pytest.mark.asyncio
async def test_agent_speaking_real_interruption_stops() -> None:
    actions = FakeActions()
    actions.add_user_speech(0.5, 2.5, "Tell me a story.")
    actions.add_llm("Here is a long story for you...", ttft=0.1, duration=0.3)
    actions.add_tts(8.0)
    actions.add_user_speech(3.0, 3.5, "no stop", stt_delay=0.1)

    session = create_session(actions, speed_factor=5.0)
    agent = MyAgent()

    agent_state_events: list[AgentStateChangedEvent] = []
    playback_finished_events: list[PlaybackFinishedEvent] = []
    session.on("agent_state_changed", agent_state_events.append)
    session.output.audio.on("playback_finished", playback_finished_events.append)

    await asyncio.wait_for(run_session(session, agent), timeout=SESSION_TIMEOUT)

    assert len(playback_finished_events) == 1
    assert playback_finished_events[0].interrupted is True

    interrupted_at = _find_first_state_after(
        agent_state_events, state="listening", after_state="speaking"
    )
    assert interrupted_at is not None


@pytest.mark.asyncio
async def test_agent_speaking_mixed_interrupt_stops() -> None:
    actions = FakeActions()
    actions.add_user_speech(0.5, 2.5, "Tell me a story.")
    actions.add_llm("Here is a long story for you...", ttft=0.1, duration=0.3)
    actions.add_tts(8.0)
    actions.add_user_speech(3.0, 3.8, "yeah okay but wait", stt_delay=0.1)

    session = create_session(actions, speed_factor=5.0)
    agent = MyAgent()

    agent_state_events: list[AgentStateChangedEvent] = []
    playback_finished_events: list[PlaybackFinishedEvent] = []
    session.on("agent_state_changed", agent_state_events.append)
    session.output.audio.on("playback_finished", playback_finished_events.append)

    await asyncio.wait_for(run_session(session, agent), timeout=SESSION_TIMEOUT)

    assert len(playback_finished_events) == 1
    assert playback_finished_events[0].interrupted is True

    interrupted_at = _find_first_state_after(
        agent_state_events, state="listening", after_state="speaking"
    )
    assert interrupted_at is not None
