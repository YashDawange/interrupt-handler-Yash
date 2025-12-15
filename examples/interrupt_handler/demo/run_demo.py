# demo/run_demo.py
import asyncio
import logging
from agent.speech_manager import SpeechManager
from agent.event_loop import InterruptHandler

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

async def fake_audio_playback(duration_s=3.0):
    # Simulate TTS playback that takes `duration_s` seconds.
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < duration_s:
        await asyncio.sleep(0.05)  # simulate audio frames
    return

async def on_interrupt_cb(text):
    print(f"[AGENT] INTERRUPT HANDLER CALLED with: '{text}'")
    # agent could respond with immediate stop confirmation
    print("[AGENT] Stopped speaking. What can I do?")

async def on_user_input_cb(text):
    print(f"[AGENT] USER INPUT (agent silent) -> '{text}'")
    # Example behavior for "yeah" when silent:
    if text.strip().lower() in ("yeah", "yep", "ok", "okay"):
        print("[AGENT] Great, let's continue.")
    else:
        print("[AGENT] Received user input:", text)

async def simulate_vad_and_stt(handler, speech_mgr, vad_delay, stt_delay, stt_text):
    """
    Simulate: VAD fires at vad_delay from now; STT arrives at stt_delay with sst_text.
    """
    await asyncio.sleep(vad_delay)
    print(f"--- VAD fired (t={vad_delay:.2f}s) ---")
    await handler.on_vad_triggered()
    await asyncio.sleep(stt_delay - vad_delay)
    print(f"--- STT arrived (t={stt_delay:.2f}s): '{stt_text}' ---")
    await handler.on_transcription(stt_text)

async def scenario_agent_speaking_ignore():
    print("\n=== Scenario: Agent speaking; user backchannels (should be ignored) ===")
    speech_mgr = SpeechManager()
    handler = InterruptHandler(speech_mgr, on_interrupt_cb, on_user_input_cb)

    # Start playing long audio in background
    play_task = asyncio.create_task(speech_mgr.play_audio(lambda: fake_audio_playback(2.5)))

    # Simulate VAD during speaking, with STT arriving shortly after
    # schedule: VAD at 0.2s, STT at 0.35s saying "yeah"
    await simulate_vad_and_stt(handler, speech_mgr, vad_delay=0.2, stt_delay=0.35, stt_text="Okay... yeah... uh-huh")

    await play_task
    print("Audio finished (no interruption expected).")

async def scenario_agent_silent_responds():
    print("\n=== Scenario: Agent silent; user says 'Yeah' (should be handled) ===")
    speech_mgr = SpeechManager()
    handler = InterruptHandler(speech_mgr, on_interrupt_cb, on_user_input_cb)

    # Agent is silent
    # Simulate VAD and STT
    await simulate_vad_and_stt(handler, speech_mgr, vad_delay=0.0, stt_delay=0.2, stt_text="Yeah")
    # small wait
    await asyncio.sleep(0.2)

async def scenario_agent_speaking_interrupt():
    print("\n=== Scenario: Agent speaking; user says 'No stop' (should interrupt) ===")
    speech_mgr = SpeechManager()
    handler = InterruptHandler(speech_mgr, on_interrupt_cb, on_user_input_cb)

    play_task = asyncio.create_task(speech_mgr.play_audio(lambda: fake_audio_playback(4.0)))

    # VAD at 0.6s, STT at 0.72s saying "no stop"
    await simulate_vad_and_stt(handler, speech_mgr, vad_delay=0.6, stt_delay=0.72, stt_text="No stop")
    # allow audio to be canceled by handler
    await asyncio.sleep(0.3)
    # ensure playback task completes
    await asyncio.sleep(0.1)
    if not play_task.done():
        print("Playback still running (unexpected). Cancelling for demo.")
        play_task.cancel()
        try:
            await play_task
        except asyncio.CancelledError:
            pass

async def scenario_mixed_input():
    print("\n=== Scenario: Agent speaking; user says 'yeah but wait' (mixed -> interrupt) ===")
    speech_mgr = SpeechManager()
    handler = InterruptHandler(speech_mgr, on_interrupt_cb, on_user_input_cb)

    play_task = asyncio.create_task(speech_mgr.play_audio(lambda: fake_audio_playback(3.0)))
    await simulate_vad_and_stt(handler, speech_mgr, vad_delay=0.25, stt_delay=0.4, stt_text="yeah but wait")
    await asyncio.sleep(0.2)
    if not play_task.done():
        print("Playback still running after mixed input (unexpected). Cancelling for demo.")
        play_task.cancel()
        try:
            await play_task
        except asyncio.CancelledError:
            pass

async def main():
    await scenario_agent_speaking_ignore()
    await asyncio.sleep(0.5)
    await scenario_agent_silent_responds()
    await asyncio.sleep(0.5)
    await scenario_agent_speaking_interrupt()
    await asyncio.sleep(0.5)
    await scenario_mixed_input()

if __name__ == "__main__":
    asyncio.run(main())
