import sys
import os

import importlib.util

# Import InterruptHandler directly from file
file_path = os.path.abspath("livekit-agents/livekit/agents/voice/interrupt_handler.py")
spec = importlib.util.spec_from_file_location("interrupt_handler", file_path)
interrupt_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interrupt_handler)
InterruptHandler = interrupt_handler.InterruptHandler

def test_interrupt_handler():
    handler = InterruptHandler()

    scenarios = [
        ("yeah", False, "Ignore word"),
        ("ok", False, "Ignore word"),
        ("hmm", False, "Ignore word"),
        ("stop", True, "Hard command"),
        ("wait", True, "Hard command"),
        ("no", True, "Hard command"),
        ("hold on", True, "Hard command"),
        ("yeah ok but wait", True, "Mixed command (contains hard command)"),
        ("random words", True, "Unknown words (default interrupt)"),
        ("okay yeah hmm", False, "Multiple ignore words"),
        ("no stop", True, "Multiple hard commands"),
    ]

    failed = False
    for transcript, expected, description in scenarios:
        result = handler.should_interrupt(transcript)
        if result != expected:
            print(f"FAIL: '{transcript}' -> Expected {expected}, got {result} ({description})")
            failed = True
        else:
            print(f"PASS: '{transcript}' -> {result} ({description})")

    if not failed:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    test_interrupt_handler()
