from interrupt_classifier import classify_text

def simulate(text, speaking):
    decision = classify_text(text, speaking)
    print(f"text='{text}', speaking={speaking} → {decision}")

print("---- agent speaking ----")
simulate("yeah", True)
simulate("ok", True)

print("---- agent silent ----")
simulate("yeah", False)

print("---- stop ----")
simulate("stop", True)
