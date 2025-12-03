import asyncio
import pytest
from types import SimpleNamespace

# adjust this import if your file path is different
from livekit.agents.voice.interrupt_handler import InterruptHandler

class DummySession:
    """
    Minimal fake session that simulates agent state + interrupt behavior.
    """
    def __init__(self, agent_state="speaking"):
        self.agent_state = agent_state
        self.interrupted = False

    def interrupt(self, *, force=False):
        """
        Simulates AgentSession.interrupt() by setting a flag.
        Returns an already-resolved Future since real code expects awaitable.
        """
        self.interrupted = True
        fut = asyncio.get_event_loop().create_future()
        fut.set_result(None)
        return fut


@pytest.mark.asyncio
async def test_ignore_soft_word_while_speaking():
    session = DummySession(agent_state="speaking")
    handler = InterruptHandler(
        session=session,
        partial_timeout=0.05,
        ignore_list=["yeah", "ok", "hmm"],
        hard_list=["stop", "wait", "no"],
    )

    # Simulate user VAD start from the same speaker
    fake_vad_event = SimpleNamespace(speaker_id="u1")
    await handler.on_vad_start(fake_vad_event)

    # Soft word (should NOT interrupt)
    await handler.on_stt_partial("yeah", speaker_id="u1")

    await asyncio.sleep(0.01)
    assert session.interrupted is False


@pytest.mark.asyncio
async def test_hard_word_interrupts_while_speaking():
    session = DummySession(agent_state="speaking")
    handler = InterruptHandler(
        session=session,
        partial_timeout=0.05,
        ignore_list=["yeah", "ok", "hmm"],
        hard_list=["stop", "wait", "no"],
    )

    fake_vad_event = SimpleNamespace(speaker_id="u1")
    await handler.on_vad_start(fake_vad_event)

    # Contains "stop" → should interrupt immediately
    await handler.on_stt_partial("no stop wait", speaker_id="u1")

    await asyncio.sleep(0.01)
    assert session.interrupted is True


@pytest.mark.asyncio
async def test_soft_word_when_agent_silent():
    session = DummySession(agent_state="listening")  # agent NOT speaking
    handler = InterruptHandler(
        session=session,
        partial_timeout=0.05,
        ignore_list=["yeah", "ok", "hmm"],
        hard_list=["stop", "wait", "no"],
    )

    fake_vad_event = SimpleNamespace(speaker_id="u1")

    # Handler should see agent is silent → no interrupt logic
    await handler.on_vad_start(fake_vad_event)

    assert session.interrupted is False
