from interrupt_handler import InterruptHandler
import threading
import time
import sys
sys.stdout.reconfigure(encoding='utf-8')
handler = InterruptHandler()
agent_is_speaking = False
stop_now = False

def agent_speak(text):
    global agent_is_speaking, stop_now
    stop_now = False
    agent_is_speaking = True
    print(f"\n🤖 Agent Speaking: {text}")

    # Simulate speaking for 6 seconds, allowing interruption
    for _ in range(6):
        if stop_now:
            break
        time.sleep(1)

    if stop_now:
        print("❌ Agent interrupted.\n")
    else:
        print("🤖 Agent finished speaking.\n")

    agent_is_speaking = False
    stop_now = False


def handle_user_input():
    global agent_is_speaking, stop_now

    while True:
        user_input = input("🟢 YOU: ")

        if user_input == "":
            continue

        if user_input.lower() == "start_talking":
            threading.Thread(target=agent_speak, args=("Let me explain something important...",)).start()
            continue

        decision = handler.process_transcript(user_input, agent_is_speaking)

        if decision == "IGNORE":
            print("🟡 Ignored (backchannel detected — agent continues talking)\n")

        elif decision == "INTERRUPT":
            if agent_is_speaking:
                print("🔴 INTERRUPTION TRIGGERED! Agent stops.\n")
                stop_now = True
            else:
                print("🟠 Interrupt request but agent already silent.\n")

        elif decision == "RESPOND":
            if agent_is_speaking:
                print("🔵 Response queued after speaking ends.\n")
            else:
                print(f"🤖 Agent Responds: Great! ('{user_input}')\n")


print("🔵 OFFLINE AI INTERRUPTION TEST SIMULATOR (REAL-TIME)")
print("Commands:")
print("- Type 'start_talking' to simulate agent speaking")
print("- Type filler words while agent speaks: yeah, ok, hmm (should IGNORE)")
print("- Type: stop, wait, no (should INTERRUPT)\n")

handle_user_input()