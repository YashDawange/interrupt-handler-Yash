
import time
from livekit.interrupt_handlers import (
    on_tts_start, on_tts_end, on_vad_detected, on_stt_result
)
from livekit.agent_state import GLOBAL_STATE

def scenario_long_explanation():
    print("\n--- Long explanation (agent speaking) ---")
    on_tts_start()
    # Simulate agent speaking (TTS playing)
    time.sleep(0.8)
    print("[USER] (while speaking) says: 'Okay... yeah'")
    on_vad_detected()               # VAD fires quickly
    time.sleep(0.15)                # STT delay
    on_stt_result("okay yeah")      # STT result arrives
    time.sleep(1.2)
    on_tts_end()

def scenario_passive_affirmation():
    print("\n--- Passive affirmation (agent silent) ---")
    time.sleep(0.4)
    print("[USER] (agent silent) says: 'Yeah'")
    on_vad_detected()
    time.sleep(0.12)
    on_stt_result("yeah")

def scenario_correction():
    print("\n--- Correction (agent speaking + 'No stop') ---")
    on_tts_start()
    time.sleep(0.5)
    print("[USER] (while speaking) says: 'No stop'")
    on_vad_detected()
    time.sleep(0.12)
    on_stt_result("no stop")
    time.sleep(0.4)
    on_tts_end()

def scenario_mixed_input():
    print("\n--- Mixed input (agent speaking + 'yeah okay but wait') ---")
    on_tts_start()
    time.sleep(0.5)
    print("[USER] (while speaking) says: 'yeah okay but wait'")
    on_vad_detected()
    time.sleep(0.18)
    on_stt_result("yeah okay but wait")
    time.sleep(0.4)
    on_tts_end()

if __name__ == "__main__":
    print("Starting interruption-handler demo.")
    scenario_long_explanation()
    scenario_passive_affirmation()
    scenario_correction()
    scenario_mixed_input()
    print("\nDemo run complete.")
