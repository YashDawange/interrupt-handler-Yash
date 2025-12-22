# interrupt_handler.py

from interrupt_config import (
    IGNORE_WORDS,
    INTERRUPT_WORDS,
    AFFIRM_WORDS,
    GREETING_WORDS,
)

def normalize(text: str) -> str:
    return text.lower().strip()

def tokenize(text: str):
    return set(normalize(text).split())

def fuzzy_greeting(text: str) -> bool:
    """
    Handles typos like:
    hel, helo, hell, hello, hi, hii
    """
    text = normalize(text)
    return text.startswith(("he", "hi", "ho", "yo"))

def classify_input(text: str) -> str:
    text = normalize(text)
    tokens = tokenize(text)

    if not text:
        return "IGNORE"

   
    for word in INTERRUPT_WORDS:
     if word in text:
        return "INTERRUPT"

    #  resume
    if tokens & AFFIRM_WORDS:
        return "AFFIRM"


    if text in GREETING_WORDS or fuzzy_greeting(text):
        return "START"

    
    if tokens and tokens.issubset(IGNORE_WORDS):
        return "IGNORE"

    
    return "RESPOND"