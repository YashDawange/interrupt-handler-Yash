from agent.basic_agent import decide_interrupt
from agent.interrupt_config import IGNORE_WORDS, INTERRUPT_WORDS


def test_single_filler_ignored():
    assert decide_interrupt(["yeah"]) == "IGNORE"


def test_multiple_fillers_ignored():
    assert decide_interrupt(["yeah", "ok", "hmm"]) == "IGNORE"


def test_single_interrupt_word():
    assert decide_interrupt(["stop"]) == "INTERRUPT"


def test_multiple_interrupt_words():
    assert decide_interrupt(["no", "stop"]) == "INTERRUPT"


def test_mixed_input_interrupts():
    assert decide_interrupt(["yeah", "but", "wait"]) == "INTERRUPT"


def test_unknown_words_interrupt():
    assert decide_interrupt(["maybe", "later"]) == "INTERRUPT"


def test_empty_tokens_interrupts():
    assert decide_interrupt([]) == "INTERRUPT"
