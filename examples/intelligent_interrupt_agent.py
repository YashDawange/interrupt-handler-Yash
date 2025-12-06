# examples/intelligent_interrupt_agent.py

from interrupt_logic import AgentState, Action, decide_action

def main():
    print("=== Intelligent Interruption Logic Demo (No API Needed) ===")
    print("Format: <STATE> | <user text>")
    print("Where STATE is SPEAKING or SILENT")
    print("Examples:")
    print("  SPEAKING | okay yeah uhhuh")
    print("  SPEAKING | wait a second")
    print("  SILENT   | yeah")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            raw = input("Enter: ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not raw:
            continue

        if raw.strip().lower() == "exit":
            print("Exiting.")
            break

        if "|" not in raw:
            print("⚠️  Please use format: SPEAKING | yeah ok")
            continue

        state_part, text_part = raw.split("|", 1)
        state_str = state_part.strip().upper()
        user_text = text_part.strip()

        # Map string to AgentState enum
        if state_str == "SPEAKING":
            agent_state = AgentState.SPEAKING
        else:
            agent_state = AgentState.SILENT

        action = decide_action(agent_state, user_text)

        print(f"  → agent_state = {agent_state.value!r}")
        print(f"  → user_text   = {user_text!r}")
        print(f"  ⇒ action      = {action.value}")
        print("-" * 50)


if __name__ == "__main__":
    main()
