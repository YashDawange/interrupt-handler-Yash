# tests/test_interrupt_filter.py

from livekit.agents.voice.interrupt_filter import InterruptFilter

f = InterruptFilter.from_env()

cases = [
    ("yeah", "expect: ignore"),
    ("ok", "expect: ignore"),
    ("yeah yeah", "expect: ignore"),
    ("stop", "expect: interrupt"),
    ("wait", "expect: interrupt"),
    ("yeah wait", "expect: interrupt"),
    ("what's the weather", "expect: neutral"),
    ("", "expect: neutral"),
]

print("InterruptFilter quick test")
print("-" * 40)

for txt, note in cases:
    result = f.classify(txt)
    print(f"'{txt}' -> {result:9} ({note})")
