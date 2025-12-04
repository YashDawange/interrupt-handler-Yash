"""
Interactive demo for live recording.
For each scenario the script will:
 - print instructions to the terminal
 - wait for you to perform the action (speak filler / press Enter to stop playback)
 - run the classifier and print the decision to the terminal
This makes it easy to record a short video showing both audio and visible logs.
"""
import importlib.machinery
import importlib.util
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "livekit-agents" / "livekit" / "agents" / "voice" / "interrupt_handler.py"
loader = importlib.machinery.SourceFileLoader("interrupt_handler", str(MOD_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
ih = importlib.util.module_from_spec(spec)
loader.exec_module(ih)

scenarios = [
    (
        "Scenario 1 - Long explanation",
        "Agent: long paragraph will play. Action: while it is speaking say loudly: 'Okay... yeah... uh-huh'. Then press ENTER when done.",
        "Okay... yeah... uh-huh",
        True,
    ),
    (
        "Scenario 2 - Passive affirmation (agent silent)",
        "Agent: silent. Action: say 'Yeah' clearly into the mic, then press ENTER.",
        "Yeah",
        False,
    ),
    (
        "Scenario 3 - Correction (stop)",
        "Agent: start speaking. Action: Say 'stop' mid-speech and then press ENTER. Also stop playback in the TTS terminal to demonstrate immediate stop.",
        "No stop",
        True,
    ),
    (
        "Scenario 4 - Mixed input",
        "Agent: speaking. Action: say 'Yeah okay but wait' and press ENTER.",
        "Yeah okay but wait",
        True,
    ),
]

print("Interactive Interrupt Demo\n")
print("Instructions:\n - Open a second terminal and run the TTS player: tools\\play_tts_interactive.ps1\n - In that TTS terminal press Enter to start/stop playback as needed for scenarios that need speech to be playing.\n - Use OBS or Game Bar to record the screen and audio (capture system audio + mic).\n")

for name, prompt, utterance, speaking in scenarios:
    print("\n=== {} ===".format(name))
    print(prompt)
    input("Press ENTER when you have performed the action (spoken the utterance and/or pressed the TTS control) -> ")
    cls = ih.classify_transcript(utterance)
    if speaking:
        if cls == "ignore":
            decision = "IGNORE (continue speaking)"
        elif cls == "interrupt":
            decision = "INTERRUPT (stop speaking)"
        else:
            decision = "UNKNOWN (conservative: IGNORE)"
    else:
        decision = "RESPOND (treat as user input)"

    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    line = f"[{ts}] {name} | utterance={utterance!r} | speaking={speaking} | class={cls} | decision={decision}"
    print(line)

print("\nDemo finished. You can stop recording now.")
