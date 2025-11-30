# Modularized LiveKit Agent Server
# Files included below. Save each section as the indicated filename in a package/folder,
# or copy them into your project. Run with: python -m livekit_agent.main

# ==========================
# File: livekit_agent/__init__.py
# ==========================

# ==========================
# File: livekit_agent/config.py
# ==========================
import logging
import os
from dotenv import load_dotenv

load_dotenv()

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
logger = logging.getLogger("livekit-agent")

# Thresholds and constants
IGNORE_WORDS = {
    "yeah", "yea", "yep", "yup", "ya", "yah",
    "ok", "okay", "k", "kk", "okey",
    "hmm", "mm", "mhm", "uh", "uhh", "umm", "um",
    "right", "sure", "cool", "fine",
    "okayyy", "okk", "okayy",
    "yes", "yess", "yesss",
    "alright", "aight",
    "gotcha", "gotchaa",
    "true", "tru", "ture",
    "huh", "aha",
}
IGNORE_PHRASES = {
    "yeah yeah",
    "yeah ok",
    "yeah okay",
    "ok ok",
    "ok okay",
    "okay okay",
    "yes yes",
    "yea yea",
    "yep yep",
    "right right",
    "mhm yeah",
    "hmm yeah",
    "okay right",
    "alright alright",
    "i see",
    "sounds good",
    "got it",
    "makes sense",
    "fair enough",
}

INTERRUPT_KEYWORDS = {
    "stop", "shut up", "no", "no stop", "wait", "hold on", "stop now", "pause",
    "cut", "listen", "someone called", "hey", "hello", "what", "why", "stop it"
}
PROFANITY_INTERRUPTS = {"shit", "damn"}

CONFIDENCE_THRESHOLD = 0.70
HIGH_CONFIDENCE_PARTIAL = 0.85
REPEATED_PASSIVE_THRESHOLD = 3
REPEATED_PASSIVE_WINDOW = 3.0
QUESTION_RESPONSE_WINDOW = 4.0
ECHO_SUPPRESSION_WINDOW = 0.35

# STT/LLM/TTS defaults (can be overridden)
DEFAULT_STT = "deepgram/nova-3"
DEFAULT_LLM = "openai/gpt-4o-mini"
DEFAULT_TTS = "cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"

