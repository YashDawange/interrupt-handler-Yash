"""
Demo script to simulate the four scenarios and produce a log file suitable for submission proof.
It doesn't require the LiveKit runtime; it calls the classifier directly and simulates AgentActivity forwarding.
"""
import os
import pathlib
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / "livekit-agents" / "livekit" / "agents" / "voice" / "interrupt_handler.py"

import importlib.machinery, importlib.util
loader = importlib.machinery.SourceFileLoader("interrupt_handler", str(MOD))
spec = importlib.util.spec_from_loader(loader.name, loader)
ih = importlib.util.module_from_spec(spec)
loader.exec_module(ih)

OUT = ROOT / "proofs"
OUT.mkdir(exist_ok=True)
LOG = OUT / "interrupt_proof.log"

lines = []

def log_case(name, user_utterance, agent_speaking):
    ts = datetime.utcnow().isoformat() + "Z"
    cls = ih.classify_transcript(user_utterance)
    # Simulate decision logic
    if agent_speaking:
        if cls == "ignore":
            decision = "IGNORE (continue speaking)"
        elif cls == "interrupt":
            decision = "INTERRUPT (stop speaking)"
        else:
            decision = "UNKNOWN (conservative: IGNORE)"
    else:
        decision = "RESPOND (treat as user input)"

    lines.append(f"[{ts}] {name} | utterance={user_utterance!r} | speaking={agent_speaking} | class={cls} | decision={decision}")


def main():
    # Only produce the three required proof scenarios per request
    log_case("Scenario 1 - Long explanation", "Okay... yeah... uh-huh", True)
    log_case("Scenario 2 - Passive affirmation (silent)", "Yeah", False)
    log_case("Scenario 3 - Correction", "No stop", True)

    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote proof log: {LOG}")

if __name__ == "__main__":
    main()
