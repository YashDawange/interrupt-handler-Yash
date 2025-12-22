import time
import threading
from interrupt_handler import classify_input


class Agent:
    def __init__(self):
        self.is_speaking = False
        self.waiting = True
        self.stop_flag = False
        self.counter = 1
        self.thread = None

    def speak_loop(self):
        self.is_speaking = True
        self.stop_flag = False

        print("\n[AGENT] Starting long explanation...\n")

        while not self.stop_flag:
            print(f"[AGENT] Explaining point {self.counter}...")
            self.counter += 1
            time.sleep(2)

        self.is_speaking = False
        print("\n[AGENT] Stopped. Listening...\n")

    def start(self):
        self.waiting = False
        self.thread = threading.Thread(target=self.speak_loop)
        self.thread.start()

    def stop_and_listen(self):
        self.stop_flag = True
        self.waiting = True
        print("[AGENT] Yes? What do you need?\n")

    def respond(self, text):
        print(f"[AGENT] Responding to user: {text}\n")


agent = Agent()

print("\n[AGENT] Hi. Are you ready?\n")
print(
    "Try inputs like:\n"
    "  hello / hi / helo\n"
    "  yeah / ok / uh-huh\n"
    "  stop / wait / hold on\n"
    "  yeah wait (mixed)\n"
    "Type 'exit' to quit.\n"
)

while True:
    user_input = input("YOU: ").strip()

    if user_input.lower() == "exit":
        agent.stop_flag = True
        break

    decision = classify_input(user_input)

    # normalize affirmations while speaking
    if agent.is_speaking and decision == "AFFIRM":
        decision = "IGNORE"

    print(
        f"[DECISION] {decision} | speaking={agent.is_speaking} waiting={agent.waiting}"
    )

    if agent.waiting:
        if decision in ("START", "AFFIRM"):
            print("\n[AGENT] Okay, starting now.\n")
            agent.start()
        elif decision == "INTERRUPT":
            agent.respond("Okay, let me know when you're ready.")
        else:
            agent.respond(user_input)
        continue

    if agent.is_speaking:
        if decision in ("IGNORE", "AFFIRM"):
            continue

        if decision == "INTERRUPT":
            agent.stop_and_listen()
            continue

        agent.respond(user_input)