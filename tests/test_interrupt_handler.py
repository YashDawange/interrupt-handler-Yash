from livekit_agents.interrupt_handler import (
    decide_interruption,
    InterruptionConfig,
    AgentState,
    InterruptionAction,
)

def test_scenario_1_backchannels():
    cfg = InterruptionConfig(["yeah","ok","hmm","uh-huh","right"], ["wait","stop","no"])
    assert decide_interruption(AgentState.SPEAKING, "Okay... yeah... uh-huh", cfg) == InterruptionAction.IGNORE

def test_scenario_2_silent_yeah():
    cfg = InterruptionConfig(["yeah","ok","hmm"], ["wait","stop","no"])
    assert decide_interruption(AgentState.SILENT, "Yeah", cfg) == InterruptionAction.RESPOND

def test_scenario_3_command_interrupt():
    cfg = InterruptionConfig(["yeah","ok"], ["wait","stop","no"])
    assert decide_interruption(AgentState.SPEAKING, "No stop", cfg) == InterruptionAction.INTERRUPT

def test_scenario_4_mixed_input():
    cfg = InterruptionConfig(["yeah","ok","hmm"], ["wait","stop","no"])
    assert decide_interruption(AgentState.SPEAKING, "Yeah okay but wait", cfg) == InterruptionAction.INTERRUPT

def test_edge_empty_transcript():
    cfg = InterruptionConfig(["yeah","ok"], ["wait","stop"])
    assert decide_interruption(AgentState.SPEAKING, "", cfg) == InterruptionAction.IGNORE
