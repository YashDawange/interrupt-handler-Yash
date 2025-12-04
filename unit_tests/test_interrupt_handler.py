from livekit_agents.interrupt_handler import (
    decide_interruption,
    InterruptionConfig,
    AgentState,
    InterruptionAction,
)

def default_cfg():
    return InterruptionConfig(
        soft_words=["yeah", "ya", "ok", "okay", "hmm", "uh-huh", "right", "mm", "mhm", "uh"],
        command_words=["wait", "stop", "no", "cancel", "hold", "pause"]
    )

def test_scenario_1_backchannels_ignored_while_speaking():
    cfg = default_cfg()
    assert decide_interruption(AgentState.SPEAKING, "Okay... yeah... uh-huh", cfg) == InterruptionAction.IGNORE

def test_scenario_2_respond_when_silent():
    cfg = default_cfg()
    assert decide_interruption(AgentState.SILENT, "Yeah", cfg) == InterruptionAction.RESPOND

def test_scenario_3_interrupt_on_command():
    cfg = default_cfg()
    assert decide_interruption(AgentState.SPEAKING, "No stop", cfg) == InterruptionAction.INTERRUPT

def test_scenario_4_mixed_input_interrupts():
    cfg = default_cfg()
    assert decide_interruption(AgentState.SPEAKING, "Yeah okay but wait", cfg) == InterruptionAction.INTERRUPT

def test_edge_empty_transcript_while_speaking_is_ignored():
    cfg = default_cfg()
    assert decide_interruption(AgentState.SPEAKING, "", cfg) == InterruptionAction.IGNORE
