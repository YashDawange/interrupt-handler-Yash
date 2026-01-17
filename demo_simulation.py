"""
demo_simulation.py

Offline demo to show how the interruption logic behaves
WITHOUT using LiveKit, STT, LLM, or TTS APIs.

Why this exists:
- API credits are limited
- Core logic should be testable independently
- Makes it easy for reviewers to verify behavior quickly

This file demonstrates:
- All assignment-required scenarios
- Extra edge cases that can break naive solutions
"""

import sys
from pathlib import Path

# Add project root to PYTHONPATH so we can import the agent module
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.basic_agent import tokenize, decide_interrupt


def simulate(agent_state: str, user_input: str):
    """
    Simulates a single interaction step.

    agent_state: "SPEAKING" or "SILENT"
    user_input : what the user says
    """
    tokens = tokenize(user_input)
    decision = decide_interrupt(tokens)

    print("\n----------------------------------------")
    print(f"Agent state : {agent_state}")
    print(f"User said   : \"{user_input}\"")
    print(f"Tokens      : {tokens}")

    if agent_state == "SPEAKING":
        if decision == "IGNORE":
            print("Decision    : IGNORE (backchannel)")
            print("Result      : Agent continues speaking")
        else:
            print("Decision    : INTERRUPT")
            print("Result      : Agent stops immediately")
    else:
        # Agent is silent → treat input as normal user turn
        print("Decision    : RESPOND")
        print("Result      : Agent responds normally")


if __name__ == "__main__":
    print("\n=== LiveKit Intelligent Interruption Demo ===")

    # =================================================
    # ASSIGNMENT-REQUIRED SCENARIOS
    # =================================================

    # Scenario 1:
    # Agent is speaking, user gives passive feedback
    simulate("SPEAKING", "yeah")

    # Scenario 2:
    # Agent is silent, same word is now a valid response
    simulate("SILENT", "yeah")

    # Scenario 3:
    # Explicit interruption command
    simulate("SPEAKING", "stop")

    # Scenario 4:
    # Mixed sentence containing an interrupt keyword
    simulate("SPEAKING", "yeah but wait")

    # =================================================
    # EXTRA EDGE CASES (SHOWING DEPTH)
    # =================================================

    # Multiple filler words
    simulate("SPEAKING", "okay yeah uh-huh")

    # Punctuation-heavy filler
    simulate("SPEAKING", "yeah, okay...")

    # Case-insensitive handling
    simulate("SPEAKING", "Yeah")

    # Unknown word while agent is speaking
    simulate("SPEAKING", "banana")

    # Polite but clear interruption
    simulate("SPEAKING", "no please stop")

    # Greeting when agent is silent
    simulate("SILENT", "hello")

    # Short confirmation when silent
    simulate("SILENT", "ok")

    # Long mixed sentence
    simulate("SPEAKING", "yeah I understand but wait a second")

