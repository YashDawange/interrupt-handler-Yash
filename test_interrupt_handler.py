from interrupt_handler import InterruptHandler

ih = InterruptHandler()

def test(text, speaking):
    ih.set_agent_speaking(speaking)
    print(f"text='{text}', speaking={speaking} -> interrupt={ih.should_interrupt(text)}")

test("yeah", True)
test("ok hmm", True)
test("stop", True)
test("yeah wait", True)
test("yeah", False)
test("hello", False)
