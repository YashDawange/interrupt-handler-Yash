from __future__ import annotations

import pytest

from livekit.agents.voice.interruptions import (
    InterruptionArbiter,
    InterruptionDecision,
    InterruptionFilterConfig,
)


class _FakeClock:
    def __init__(self) -> None:
        self._now = 0.0

    def advance(self, value: float) -> None:
        self._now += value

    def __call__(self) -> float:
        return self._now


def _make_config() -> InterruptionFilterConfig:
    return InterruptionFilterConfig(
        ignore_phrases=("yeah", "ok", "okay", "hmm", "uh huh", "right"),
        command_phrases=("stop", "wait", "hold on", "no", "but wait"),
        semantic_model=None,
        semantic_threshold=0.7,
        false_start_delay=0.05,
    )


def _make_arbiter(clock: _FakeClock) -> InterruptionArbiter:
    arbiter = InterruptionArbiter(config=_make_config(), clock=clock)
    return arbiter


def test_acknowledgement_is_ignored_during_agent_speech() -> None:
    clock = _FakeClock()
    arbiter = _make_arbiter(clock)
    arbiter.update_agent_state(speaking=True)
    arbiter.on_user_speech_detected()
    clock.advance(0.02)
    decision = arbiter.handle_transcript("ok yeah uh huh", is_final=True, user_still_speaking=True)

    assert decision == InterruptionDecision.IGNORE
    assert arbiter.should_commit_turn("ok yeah uh huh") is False


def test_affirmation_is_consumed_when_agent_is_listening() -> None:
    clock = _FakeClock()
    arbiter = _make_arbiter(clock)
    arbiter.update_agent_state(speaking=False)
    arbiter.on_user_speech_detected()

    decision = arbiter.handle_transcript("yeah", is_final=True, user_still_speaking=False)

    assert decision == InterruptionDecision.RESPOND_LISTENING
    assert arbiter.should_commit_turn("yeah") is True


def test_hard_command_interrupts_immediately() -> None:
    clock = _FakeClock()
    arbiter = _make_arbiter(clock)
    arbiter.update_agent_state(speaking=True)
    arbiter.on_user_speech_detected()
    clock.advance(0.2)

    decision = arbiter.handle_transcript("stop stop", is_final=False, user_still_speaking=True)
    assert decision == InterruptionDecision.INTERRUPT


def test_mixed_input_with_command_interrupts() -> None:
    clock = _FakeClock()
    arbiter = _make_arbiter(clock)
    arbiter.update_agent_state(speaking=True)
    arbiter.on_user_speech_detected()
    clock.advance(0.1)

    decision = arbiter.handle_transcript(
        "yeah okay but wait a second", is_final=True, user_still_speaking=True
    )
    assert decision == InterruptionDecision.INTERRUPT


@pytest.mark.parametrize(
    "utterance,expected",
    [
        ("yeah", InterruptionDecision.IGNORE),
        ("okie dokie stop", InterruptionDecision.INTERRUPT),
        ("hold on please", InterruptionDecision.INTERRUPT),
    ],
)
def test_classifier_basic_decisions(utterance: str, expected: InterruptionDecision) -> None:
    clock = _FakeClock()
    arbiter = _make_arbiter(clock)
    arbiter.update_agent_state(speaking=True)
    arbiter.on_user_speech_detected()
    clock.advance(0.2)

    assert (
        arbiter.handle_transcript(utterance, is_final=True, user_still_speaking=True) == expected
    )

