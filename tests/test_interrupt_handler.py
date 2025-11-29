# tests/test_interrupt_handler.py
import pytest
from livekit.agents.voice import interrupt_handler

@pytest.mark.asyncio
async def test_interrupt_on_stop_word():
    async def get_transcript():
        return "stop in the middle"

    called = {"interrupt": False}

    async def on_interrupt():
        called["interrupt"] = True

    async def on_ignore():
        pass

    result = await interrupt_handler.enqueue_potential_interrupt(
        get_transcript=get_transcript,
        agent_is_speaking=True,
        on_interrupt=on_interrupt,
        on_ignore=on_ignore,
        timeout_ms=200,
        logger=lambda *args, **kwargs: None,
    )

    assert result["decision"] == "INTERRUPT"
    assert called["interrupt"] is True