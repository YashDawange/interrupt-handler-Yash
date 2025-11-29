import time
import asyncio
import sys

from livekit.agents.voice import interrupt_handler

RECENT_WINDOW = 4.0

def clear_line():
    sys.stdout.write("\033[2K")
    sys.stdout.flush()

def move_up(n=1):
    sys.stdout.write(f"\033[{n}A")
    sys.stdout.flush()

def move_down(n=1):
    sys.stdout.write(f"\033[{n}B")
    sys.stdout.flush()

def print_status(agent_speaking: bool):
    clear_line()
    status = "SPEAKING" if agent_speaking else "SILENT"
    sys.stdout.write(f"Agent Status: {status}\n")
    sys.stdout.flush()


async def main():
    agent_speaking = True
    last_speech_end = None

    print_status(agent_speaking)
    print("You> ", end="", flush=True)

    while True:
        user_text = await asyncio.to_thread(input, "")

        move_up(1)
        print_status(agent_speaking)

        print(f"You> {user_text}")

        now = time.time()
        was_recent = (
            last_speech_end is not None
            and (now - last_speech_end) < RECENT_WINDOW
        )

        decision = await interrupt_handler.decide_action(
            transcript=user_text,
            agent_is_speaking=agent_speaking,
            was_speaking_recently=was_recent
        )

        print(f"[decision] {decision}")

        if decision["decision"] == "INTERRUPT":
            agent_speaking = False
            last_speech_end = time.time()
            print("[Agent] stops speaking")

        elif decision["decision"] == "IGNORE":
            print("[Agent] ignores")

        elif decision["decision"] == "RESPOND":
            mode = decision.get("mode", "once")

            if mode == "continue":
                print(f"[Agent] Respond (continuing speech): '{user_text}'")
                agent_speaking = True

            else:
                print(f"[Agent] Respond once: '{user_text}'")
                agent_speaking = False
                last_speech_end = time.time()
                
        move_up(2)
        print_status(agent_speaking)
        move_down(1)
        print("You> ", end="", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting cleanly.")