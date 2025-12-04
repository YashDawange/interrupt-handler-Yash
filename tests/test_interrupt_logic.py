import importlib.util
import sys
from pathlib import Path

# import the demo module by path
here = Path(__file__).parent.parent
script_path = here / "scripts" / "interrupt_demo.py"
spec = importlib.util.spec_from_file_location("interrupt_demo", script_path)
interrupt_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interrupt_demo)  # type: ignore


def test_should_ignore_backchannel_while_speaking():
    assert interrupt_demo.should_interrupt(True, "yeah") is False
    assert interrupt_demo.should_interrupt(True, "okay") is False
    assert interrupt_demo.should_interrupt(True, "uh-huh") is False


def test_should_interrupt_for_stop_while_speaking():
    assert interrupt_demo.should_interrupt(True, "stop") is True
    assert interrupt_demo.should_interrupt(True, "no stop") is True


def test_should_accept_user_response_when_silent():
    assert interrupt_demo.should_interrupt(False, "yeah") is True
    assert interrupt_demo.should_interrupt(False, "ok") is True


def test_mixed_input_interrupts():
    assert interrupt_demo.should_interrupt(True, "yeah but wait") is True
    assert interrupt_demo.should_interrupt(True, "ok wait") is True
