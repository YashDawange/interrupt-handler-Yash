import logging
import os
import time
from livekit.agents import vad, stt
from rapidfuzz import process, fuzz

logger = logging.getLogger("interrupt-logic")

# Configuration

# 1. Vocabulary Lists
BACKCHANNELS = {
    "yeah", "yep", "yup", "yes", "yea", "yeh",
    "uh-huh", "mm-hmm", "mhmm", "uhuh", 
    "ok", "okay", "kay", "k", "okey",
    "right", "alright", "sure", "correct", "indeed", 
    "cool", "nice", "great", "awesome", "aha", "aye"
}

CONTINUE_PHRASES = [
    "go on", "keep going", "continue", "please continue", 
    "move on", "next", "go ahead", "carry on", 
    "keep talking", "im listening", "tell me more"
]

MOTION_WORDS = {
    "go", "on", "ahead", "continue", "move", "next"
}

# 2. Parameters
MAX_BACKCHANNEL_DURATION = 1.5  # Seconds
MAX_WORD_COUNT = 5              # Words
FUZZY_SCORE_THRESHOLD = 80      # 0-100 Score

def clean_text(text: str) -> str:
    return text.strip().lower().replace(".", "").replace(",", "").replace("!", "").replace("?", "")

def is_fuzzy_match(word: str, candidates: set, threshold=FUZZY_SCORE_THRESHOLD) -> bool:
    if not word: return False
    result = process.extractOne(word, candidates, scorer=fuzz.ratio)
    if result:
        _, score, _ = result
        return score >= threshold
    return False

def check_phrase_in_text(phrase_set, text):
    return any(phrase in text for phrase in phrase_set)

def setup_interrupt_logic(agent_activity):
    logger.info("Initializing Logic: Priority System + RapidFuzz Intent Analysis")
    
    # Capture the ORIGINAL methods before we overwrite them
    original_on_vad = agent_activity.on_vad_inference_done
    original_on_interim = agent_activity.on_interim_transcript
    
    # Logic 1: Intelligent VAD (The Safety Net)
    def custom_on_vad(ev: vad.VADEvent):
        # 1. Length Check: If speech is too long, interrupt immediately.
        if ev.speech_duration > MAX_BACKCHANNEL_DURATION:
            is_agent_speaking = (
                agent_activity._current_speech is not None 
                and not agent_activity._current_speech.done()
            )
            if is_agent_speaking:
                logger.info(f"VAD Safety Net: Duration ({ev.speech_duration:.2f}s) > Limit. Interrupting.")
                agent_activity._interrupt_by_audio_activity()
        
        # We do NOT call original_on_vad here, because the original logic 
        # interrupts immediately on any sound. We want to suppress that.
        pass

    # Logic 2: Intent-Aware STT (The Brain)
    def custom_on_interim(ev: stt.SpeechEvent, *, speaking: bool | None = None):
        start_time = time.perf_counter()
        
        if not ev.alternatives or not ev.alternatives[0].text:
            return

        raw_text = ev.alternatives[0].text
        cleaned = clean_text(raw_text)
        words = cleaned.split()
        
        is_agent_speaking = (
            agent_activity._current_speech is not None 
            and not agent_activity._current_speech.done()
        )

        should_interrupt = True # Default assumption: User speaking = Interruption

        if is_agent_speaking:
            # Check 0: Length Safety Net
            if len(words) > MAX_WORD_COUNT:
                logger.info(f"Interruption (Length): '{raw_text}' (Too many words)")
                agent_activity._interrupt_by_audio_activity()
                return

            # Check 1: Priority - Explicit Continuation
            if check_phrase_in_text(CONTINUE_PHRASES, cleaned):
                should_interrupt = False
                logger.info(f"Ignoring (Explicit Continue): '{raw_text}'")

            # Check 2: Standard Backchannels (Fuzzy)
            elif cleaned in BACKCHANNELS or is_fuzzy_match(cleaned, BACKCHANNELS):
                should_interrupt = False
                logger.info(f"Ignoring (Backchannel): '{raw_text}'")

            # Check 3: Multi-Word Logic
            elif words:
                last_word = words[-1]
                
                # Sub-Check 3a: Last word indicates continuation ("Yeah wait go")
                if is_fuzzy_match(last_word, BACKCHANNELS) or is_fuzzy_match(last_word, MOTION_WORDS):
                     should_interrupt = False
                     logger.info(f"Ignoring (Last-Word Intent): '{raw_text}' -> Ends with '{last_word}'")
                
                # Sub-Check 3b: All words are backchannels
                elif all((w in BACKCHANNELS or is_fuzzy_match(w, BACKCHANNELS)) for w in words):
                    should_interrupt = False
                    logger.info(f"Ignoring (All-Backchannel): '{raw_text}'")

            # EXECUTION
            if should_interrupt:
                logger.info(f"Valid Interruption: '{raw_text}'")
                agent_activity._interrupt_by_audio_activity()
        
        # Telemetry
        process_time = (time.perf_counter() - start_time) * 1000
        if process_time > 0.5: 
            logger.debug(f"Logic Latency: {process_time:.2f}ms")

        # CRITICAL FIX HERE: Call the ORIGINAL method, not the new one
        original_on_interim(ev, speaking=speaking)

    # Inject
    agent_activity.on_vad_inference_done = custom_on_vad
    agent_activity.on_interim_transcript = custom_on_interim
    logger.info("Interruption logic injected successfully")