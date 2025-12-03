import asyncio

from examples.voice_agents.interrupt_handler import (
    InterruptHandler,
    IGNORE_WORDS,
    INTERRUPT_WORDS,
)


class FakeSession:
    """
    Minimal fake session with the APIs InterruptHandler expects:
      - async interrupt(force=True)
      - on(event_name) decorator for handler registration
    """
    def __init__(self):
        self.interrupted = False
        self._handlers = {}

    async def interrupt(self, force: bool = True):
        # This is what the handler calls when it decides to interrupt
        self.interrupted = True

    def on(self, event_name: str):
        # Called in InterruptHandler.__init__ like: session.on("user_input_transcribed")(handler)
        def decorator(fn):
            # we just store the handler in case we ever want to call it,
            # but for these tests we’ll call the private methods directly.
            self._handlers.setdefault(event_name, []).append(fn)
            return fn
        return decorator


# Simple event object for tests
class FakeTranscribedEvent:
    def __init__(self, transcript: str, is_final: bool = True):
        self.transcript = transcript
        self.is_final = is_final


async def run_single_test(name: str, transcript: str, speaking: bool, expected_interrupt: bool):
    session = FakeSession()
    handler = InterruptHandler(session)

    # Force the speaking state for this scenario
    handler.speaking = speaking

    # Create a fake user_input_transcribed event
    event = FakeTranscribedEvent(transcript=transcript, is_final=True)

    # Call the handler's private method directly
    handler._on_user_input_transcribed(event)  # type: ignore[attr-defined]

    # Let any scheduled asyncio tasks run (create_task calls inside handler)
    await asyncio.sleep(0.1)

    actual = session.interrupted
    result = "PASS" if actual == expected_interrupt else "FAIL"
    print(
        f"{name:40s} | speaking={speaking:<5} | transcript={transcript!r:<25} "
        f"| interrupted={actual} (expected={expected_interrupt}) -> {result}"
    )


async def main():
    print("\n==== InterruptHandler Tests ====\n")
    print(f"IGNORE_WORDS   = {sorted(IGNORE_WORDS)}")
    print(f"INTERRUPT_WORDS = {sorted(INTERRUPT_WORDS)}\n")

    # SCENARIO 1: Backchannels while agent is speaking → should NOT interrupt
    await run_single_test(
        "Ignore backchannel: 'yeah' while speaking",
        "yeah",
        speaking=True,
        expected_interrupt=False,
    )
    await run_single_test(
        "Ignore backchannel: 'ok' while speaking",
        "ok",
        speaking=True,
        expected_interrupt=False,
    )

    # SCENARIO 2: Pure interrupt keywords while speaking → MUST interrupt
    await run_single_test(
        "Interrupt: 'stop' while speaking",
        "stop",
        speaking=True,
        expected_interrupt=True,
    )
    await run_single_test(
        "Interrupt: 'wait' while speaking",
        "wait",
        speaking=True,
        expected_interrupt=True,
    )

    # SCENARIO 3: Mixed sentence with interrupt word while speaking → MUST interrupt
    await run_single_test(
        "Mixed: 'yeah wait okay' while speaking",
        "yeah wait okay",
        speaking=True,
        expected_interrupt=True,
    )

    # SCENARIO 4: Backchannel when agent is NOT speaking → should NOT interrupt
    # (In a real app this would be processed as normal user input)
    await run_single_test(
        "Silent agent, user says 'yeah'",
        "yeah",
        speaking=False,
        expected_interrupt=False,
    )

    # SCENARIO 5: Normal sentence (non-backchannel) while speaking → interrupt
    await run_single_test(
        "Normal sentence while speaking",
        "I have a question about your answer",
        speaking=True,
        expected_interrupt=True,
    )

    print("\n==== Tests Completed ====\n")


if __name__ == "__main__":
    asyncio.run(main())
