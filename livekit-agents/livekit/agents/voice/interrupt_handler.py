from __future__ import annotations

import os
import re
import asyncio
from typing import Set

# Load configuration from environment with sane defaults
IGNORE_WORDS: Set[str] = {
    w.strip().lower()
    for w in os.getenv("LIVEKIT_IGNORE_WORDS", "yeah,ok,okay,hmm,right,uh-huh,uhh,mm,uh").split(",")
    if w.strip()
}

COMMAND_WORDS: Set[str] = {
    w.strip().lower()
    for w in os.getenv(
        "LIVEKIT_COMMAND_WORDS",
        "stop,wait,hold,pause,wait a second,no,stop that,start,hello,cancel,wait,stop",
    ).split(",")
    if w.strip()
}

# milliseconds to wait for a fast STT partial before deciding
VALIDATION_WINDOW_MS = int(os.getenv("LIVEKIT_VALIDATION_WINDOW_MS", "200"))


def normalize_transcript(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s'-]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def classify_transcript(transcript: str) -> str:
    """
    Classify the transcript into: 'ignore', 'interrupt', or 'unknown'.

    - 'ignore': transcript contains only filler/ignore words
    - 'interrupt': transcript contains any command word/phrase
    - 'unknown': otherwise (treat as possible meaningful speech)
    """
    text = normalize_transcript(transcript)
    if not text:
        return "unknown"

    tokens = text.split()

    # If any command phrase appears anywhere in text, treat as interrupt
    for cmd in COMMAND_WORDS:
        if cmd in text or cmd in tokens:
            return "interrupt"

    # If every token is an ignore word, classify as ignore
    if all(tok in IGNORE_WORDS for tok in tokens):
        return "ignore"

    return "unknown"


async def defer_vad_decision(audio_recognition, speaking: bool) -> str:
    """
    Wait a short validation window for STT to produce a fast partial transcript.
    Returns classification string same as classify_transcript.

    audio_recognition: the AudioRecognition instance (has .current_transcript)
    speaking: whether agent was speaking at the time of VAD trigger
    """
    # Quick-read current transcript first
    transcript = ""
    try:
        # Try to get any immediate transcript available
        transcript = audio_recognition.current_transcript
    except Exception:
        transcript = ""

    if transcript:
        return classify_transcript(transcript)

    # Wait a tiny window for STT partials (non-blocking)
    try:
        await asyncio.sleep(VALIDATION_WINDOW_MS / 1000.0)
    except asyncio.CancelledError:
        return "unknown"

    try:
        transcript = audio_recognition.current_transcript
    except Exception:
        transcript = ""

    if transcript:
        return classify_transcript(transcript)

    # no transcript available within window
    # conservative default: if agent was speaking, assume filler (ignore);
    # if agent was silent, treat as unknown so caller will process it
    return "ignore" if speaking else "unknown"
