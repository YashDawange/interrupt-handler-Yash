from interrupt_classifier import classify_text

def simulate(text, speaking):
    decision = classify_text(text, speaking)
    print(f"text='{text}', speaking={speaking} and the decision is {decision}")

print(" agent is speaking ")
simulate("yeah", True)
simulate("ok", True)

print(" agent is silent ")
simulate("yeah", False)

print(" stop ")
simulate("stop", True)
