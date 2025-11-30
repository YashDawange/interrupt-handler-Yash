"""Test the interruption filter logic."""
import sys
import os

# Add livekit-agents to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "livekit-agents"))

from livekit.agents.voice.interrupt_filter import InterruptionFilter

print("🧪 Testing Interruption Filter\n")

filter = InterruptionFilter()

tests = [
    ("yeah", True, False),  # (text, agent_speaking, should_interrupt?)
    ("ok", True, False),
    ("stop", True, True),
    ("wait", True, True),
    ("yeah but wait", True, True),
    ("yeah", False, True),  # Agent silent - process it
]

passed = 0
failed = 0

for text, speaking, expected_interrupt in tests:
    decision = filter.should_allow_interruption(text, speaking)
    match = "YES" if (decision.should_interrupt == expected_interrupt) else "NO"
    
    if decision.should_interrupt == expected_interrupt:
        passed += 1
    else:
        failed += 1
    
    print(f"{match} '{text}' (speaking={speaking}) → interrupt={decision.should_interrupt}")
    print(f"   Reason: {decision.reason}\n")

print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)