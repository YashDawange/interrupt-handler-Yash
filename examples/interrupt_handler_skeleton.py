"""
interrupt_handler_skeleton.py
A simple, self-contained logic skeleton demonstrating the "ignore vs interrupt"
decision layer. This file is a starting point — you (or I) will integrate it
with the agent's VAD / STT event handlers in the repo.

This is intentionally independent so you can show it in the PR and explain
how you'd wire it to the repo's STT/VAD callbacks.
"""

import asyncio
import re

SOFT_WORDS = {"yeah", "ok", "okay", "hmm", "uh-huh", "right", "uhuh"}
HARD_WORDS = {"wait", "stop", "no", "hold", "hold on", "pause", "stop now"}

# simple state tracker (replace with event callbacks in actual integration)
agent_is_speaking = False

def on_tts_start():
    global agent_is_speaking
    agent_is_speaking = True
    print("[STATE] TTS started; agent_is_speaking = True")

def on_tts_end():
    global agent_is_speaking
    agent_is_speaking = False
    print("[STATE] TTS ended; agent_is_speaking = False")

async def handle_possible_interruption(stt_queue, interrupt_callback, ignore_callback, timeout=0.15):
    """
    stt_queue: asyncio.Queue where STT transcripts are put by STT handler.
    interrupt_callback: callable to run when we decide to interrupt.
    ignore_callback: callable to run when we decide to ignore (continue speaking).
    timeout: how long to wait for STT after VAD.
    """
    global agent_is_speaking

    # If agent not speaking, do nothing special — upstream code will handle user input.
    if not agent_is_speaking:
        return

    try:
        stt_text = await asyncio.wait_for(stt_queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        # No transcript arrived quickly -> conservative choice: perform interrupt
        interrupt_callback("timeout - no stt")
        return

    text = (stt_text or "").strip().lower()
    if not text:
        interrupt_callback("empty transcript")
        return

    # tokenize simply
    tokens = set(re.findall(r"\b[\w'-]+\b", text))

    # If any HARD_WORD present -> interrupt
    if tokens & HARD_WORDS:
        interrupt_callback(f"hard word in '{text}'")
        return

    # If tokens consist only of SOFT_WORDS -> ignore
    if tokens and tokens <= SOFT_WORDS:
        ignore_callback(f"soft words only: '{text}'")
        return

    # Mixed input: if contains many words or isn't pure soft -> interrupt
    if len(text.split()) > 2:
        interrupt_callback(f"mixed/long input: '{text}'")
        return

    # default: ignore short ambiguous inputs
    ignore_callback(f"default ignore for '{text}'")
