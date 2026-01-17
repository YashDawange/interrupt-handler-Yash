from agent.basic_agent import FSMState, decide_interrupt, tokenize


def simulate(fsm_state, text):
    if fsm_state != FSMState.POTENTIAL_INTERRUPT:
        return "NOOP"

    tokens = tokenize(text)
    return decide_interrupt(tokens)


# -----------------------------
# Scenario 1: Long Explanation
# -----------------------------
def test_scenario_1_ignore_backchannel():
    result = simulate(FSMState.POTENTIAL_INTERRUPT, "okay yeah uh-huh")
    assert result == "IGNORE"


# -----------------------------
# Scenario 2: Passive Affirmation
# -----------------------------
def test_scenario_2_filler_when_silent():
    result = simulate(FSMState.SILENT, "yeah")
    assert result == "NOOP"


# -----------------------------
# Scenario 3: Correction
# -----------------------------
def test_scenario_3_stop_interrupts():
    result = simulate(FSMState.POTENTIAL_INTERRUPT, "no stop")
    assert result == "INTERRUPT"


# -----------------------------
# Scenario 4: Mixed Input
# -----------------------------
def test_scenario_4_mixed_interrupt():
    result = simulate(FSMState.POTENTIAL_INTERRUPT, "yeah okay but wait")
    assert result == "INTERRUPT"
