import asyncio
from livekit.agents.voice.interrupt_handler import InterruptHandler

# --------------------------
# MOCKS
# --------------------------

class FakePlayer:
    def __init__(self):
        self.stopped = False
        self.is_speaking = True

    async def stop(self):
        print("[PLAYER] stop() called")
        self.stopped = True

    def is_playing(self):
        return self.is_speaking


class FakeLLM:
    def __init__(self):
        self.cancelled = False

    async def cancel(self):
        print("[LLM] cancel() called")
        self.cancelled = True


class FakeSession:
    def __init__(self):
        self.player = FakePlayer()
        self.llm = FakeLLM()
        self.events = []
        self.user_state = "listening"
        self.agent_state = "speaking"
        self.last_user_text = None

        self.interrupt_handler = InterruptHandler(
            get_agent_state_callable=lambda: self.player.is_playing()
        )

        # Patch interrupt callback
        self.interrupt_handler._do_interrupt = (
            lambda sid, transcript="", reason="": asyncio.create_task(
                self._on_interrupt(transcript, reason)
            )
        )

    def emit(self, event_type, event):
        print(f"[EVENT] {event_type} -> {event}")
        self.events.append((event_type, event))

    async def _on_interrupt(self, transcript, reason):
        print(f"[SESSION] INTERRUPT '{transcript}' ({reason})")

        # Stop TTS
        await self.player.stop()

        # Cancel LLM
        await self.llm.cancel()

        self.last_user_text = transcript
        self.agent_state = "listening"


# --------------------------
# TESTS
# --------------------------

async def test_stt_interrupts():
    print("\n===== TEST 1: STT INTERRUPT LOGIC =====")
    session = FakeSession()

    # ignore-words
    res1 = await session.interrupt_handler.on_transcript("demo", "yeah ok", False)
    print("IGNORE RESULT:", res1)

    # pure interrupt word
    res2 = await session.interrupt_handler.on_transcript("demo", "stop now", True)
    print("PURE INTERRUPT RESULT:", res2)

    # mixed phrase
    res3 = await session.interrupt_handler.on_transcript("demo", "yeah but wait", True)
    print("MIXED RESULT:", res3)


async def test_vad_interrupts():
    print("\n===== TEST 2: VAD INTERRUPT LOGIC =====")
    session = FakeSession()

    res = await session.interrupt_handler.on_vad_start("demo")
    print("VAD RESULT:", res)


async def test_pipeline_full_flow():
    print("\n===== TEST 3: FULL PIPELINE =====")
    session = FakeSession()

    result = await session.interrupt_handler.on_transcript(
        "demo", "yeah but stop please", True
    )

    print("HANDLER RESULT:", result)
    print("PLAYER STOPPED:", session.player.stopped)
    print("LLM CANCELLED:", session.llm.cancelled)
    print("USER TEXT:", session.last_user_text)
    print("NEW AGENT STATE:", session.agent_state)


async def test_event_emission():
    print("\n===== TEST 4: EVENT EMISSION =====")
    session = FakeSession()

    # we simulate event emission manually
    session.emit("user_input_transcribed", {"text": "hello"})
    session.emit("agent_state_changed", {"old": "speaking", "new": "thinking"})
    session.emit("conversation_item_added", {"msg": "Hi user"})

    print("EVENTS RECORDED:", session.events)


async def test_state_transitions():
    print("\n===== TEST 5: STATE TRANSITIONS =====")
    session = FakeSession()

    # On interrupt, session.agent_state must change to "listening"
    await session.interrupt_handler.on_transcript("demo", "stop", True)

    print("FINAL SESSION STATE:", session.agent_state)


async def test_llm_cancel_behavior():
    print("\n===== TEST 6: LLM CANCEL BEHAVIOR =====")
    session = FakeSession()

    await session.interrupt_handler.on_transcript("demo", "stop please", True)

    print("LLM CANCELLED:", session.llm.cancelled)


# ------------------------------------
# RUN ALL TESTS
# ------------------------------------
async def main():
    await test_stt_interrupts()
    await test_vad_interrupts()
    await test_pipeline_full_flow()
    await test_event_emission()
    await test_state_transitions()
    await test_llm_cancel_behavior()

asyncio.run(main())
