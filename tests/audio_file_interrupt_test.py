# tests/audio_file_interrupt_test.py

import os
import speech_recognition as sr
from livekit.agents.voice.interrupt_filter import InterruptFilter

r = sr.Recognizer()
filt = InterruptFilter.from_env()

AUDIO_CASES = [
    ("backchannel_yes.wav", "backchannel ('yeah okay') - expect: ignore"),
    ("interrupt_stop.wav", "explicit interrupt ('wait') - expect: interrupt"),
    ("neutral_question.wav", "neutral question ('what's the weather today') - expect: neutral"),
    ("mixed_wait.wav", "mixed ('yeah wait a second') - expect: interrupt"),
]

BASE_DIR = os.path.dirname(__file__)


def run_case(filename: str, note: str):
    path = os.path.join(BASE_DIR, filename)

    if not os.path.exists(path):
        print(f"[SKIP] {filename} not found ({note})")
        return

    print(f"\n=== Testing file: {filename} ({note}) ===")

    with sr.AudioFile(path) as source:
        audio = r.record(source)

    try:
        text = r.recognize_google(audio)
        cls = filt.classify(text)
        print(f"Recognized text: {text!r}")
        print(f"InterruptFilter result: {cls}")
    except sr.UnknownValueError:
        print("SpeechRecognition: could not understand audio")
    except sr.RequestError as e:
        print(f"SpeechRecognition API error: {e}")


if __name__ == "__main__":
    print("Real audio → STT → InterruptFilter demo\n")
    for fname, note in AUDIO_CASES:
        run_case(fname, note)
