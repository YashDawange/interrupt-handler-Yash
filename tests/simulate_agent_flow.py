
from time import sleep
from livekit.agents.voice.interrupt_filter import InterruptFilter


class MockSession:
    def __init__(self, state: str):
        # simple placeholder for agent_state
        self.agent_state = state


def simulate(transcript: str, session: MockSession, filt: InterruptFilter):
    cls = filt.classify(transcript)
    print(f"[agent_state={session.agent_state:8}] user said: '{transcript}' -> {cls}")

    if session.agent_state == "speaking":
        if cls == "ignore":
            print("  ⇒ decision: IGNORE (don't interrupt agent)\n")
        elif cls == "interrupt":
            print("  ⇒ decision: INTERRUPT (stop agent speaking)\n")
        else:
            print("  ⇒ decision: treat as real input (may interrupt based on other logic)\n")
    else:
        print("  ⇒ decision: agent is idle → handle as normal user input\n")


if __name__ == "__main__":
    filt = InterruptFilter.from_env()

    # ----------------------------
    # Scenario 1: Agent is SPEAKING
    # ----------------------------
    speaking_session = MockSession("speaking")

    print("=== Scenario 1: Agent is SPEAKING (backchannels) ===\n")
    backchannels = [
        "yeah",
        "ok",
        "okay",
        "hmm",
        "mmhmm",
        "right",
        "yeah yeah",
        "  ok   "         # extra spaces

    ]
    for t in backchannels:
        simulate(t, speaking_session, filt)
        sleep(2)

    print("=== Scenario 1b: Agent is SPEAKING (explicit interrupts) ===\n")
    interrupts = [
        "stop",
        "STOP",                     # all caps
        "wait",
        "please stop talking",
        "can you wait a second",
        "no no no",
        "hold on",
        "hang on for a sec",
        "pause",
        "pause please",
        "yeah wait",                # ignore + interrupt
    ]
    for t in interrupts:
        simulate(t, speaking_session, filt)
        sleep(2)

    print("=== Scenario 1c: Agent is SPEAKING (neutral / mixed phrases) ===\n")
    neutral_when_speaking = [
        "what's the weather today",
        "tell me a joke",
        "can you help me with my homework",
        "yeah what is the weather",   # ignore + neutral → neutral
        "ok so what do you think",
        "right now I want to know about movies",
        "",                           # empty
        "   ",                        # whitespace only
    ]
    for t in neutral_when_speaking:
        simulate(t, speaking_session, filt)
        sleep(2)

    # ----------------------------
    # Scenario 2: Agent is IDLE
    # ----------------------------
    idle_session = MockSession("idle")

    print("\n=== Scenario 2: Agent is IDLE (same phrases) ===\n")
    idle_inputs = [
        "yeah",
        "ok",
        "stop",
        "wait",
        "hold on",
        "what's the weather today",
        "tell me a joke",
        "hello there",
        "hmm",
        "yeah wait",
    ]
    for t in idle_inputs:
        simulate(t, idle_session, filt)
        sleep(2)

    # ----------------------------
    # Scenario 3: Simulated mini-conversation
    # ----------------------------
    print("\n=== Scenario 3: Mini conversation flow ===\n")
    convo_session = MockSession("speaking")
    convo_flow = [
        "yeah",                     # user just acknowledges → ignore
        "ok",                       # ignore
        "what's the weather today", # neutral
        "stop",                     # strong interrupt
        "hmm",                      # ignore if agent is still speaking
        "wait I changed my mind",   # interrupt
    ]

    for t in convo_flow:
        simulate(t, convo_session, filt)
        sleep(2)
