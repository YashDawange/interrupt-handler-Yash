#!/usr/bin/env python3
"""
Simple offline demo that uses the same decision heuristics as the agent
code to demonstrate the four required scenarios.
"""
import os
import re

IGNORE_WORDS = [w.strip().lower() for w in os.getenv("AGENT_IGNORE_WORDS", "yeah,ok,okay,hmm,right,uh-huh,uh,mmhmm,mhm").split(",")]
INTERRUPT_WORDS = [w.strip().lower() for w in os.getenv("AGENT_INTERRUPT_WORDS", "wait,stop,no").split(",")]


def tokenize(text: str):
    if not text:
        return []
    return [t.strip("'\"") for t in re.findall(r"[\w'-]+", text.lower())]


def should_interrupt(agent_speaking: bool, transcript: str) -> bool:
    tokens = tokenize(transcript)
    if not tokens:
        return False

    ignore_set = set(IGNORE_WORDS)
    interrupt_set = set(INTERRUPT_WORDS)

    if agent_speaking:
        if any(tok in interrupt_set for tok in tokens):
            return True
        if all(tok in ignore_set for tok in tokens):
            return False
        # mixed content -> interrupt
        return True
    else:
        # agent silent: treat input as valid
        return True


SCENARIOS = [
    (
        "Long explanation — user backchannels while agent speaks",
        True,
        "okay yeah uh-huh",
        False,
    ),
    (
        "Passive affirmation — agent silent, user says 'yeah'",
        False,
        "yeah",
        True,
    ),
    (
        "Correction — agent speaks, user says 'no stop'",
        True,
        "no stop",
        True,
    ),
    (
        "Mixed input — agent speaks, user says 'yeah okay but wait'",
        True,
        "yeah okay but wait",
        True,
    ),
]


if __name__ == "__main__":
    for title, speaking, text, expected in SCENARIOS:
        result = should_interrupt(speaking, text)
        print(f"Scenario: {title}")
        print(f" Agent speaking: {speaking}")
        print(f" User speech: '{text}'")
        print(f" Decision: {'INTERRUPT' if result else 'IGNORE'} (expected: {'INTERRUPT' if expected else 'IGNORE'})")
        print("---")
