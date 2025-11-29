import asyncio
import os
import re
from typing import Callable, Iterable, Optional

# --- config via env (comma-separated) ---
def _parse(raw: str) -> list[str]:
    return [x.strip().lower().replace("-", " ") for x in raw.split(",") if x.strip()]

raw_ignore = os.getenv("INTERRUPT_IGNORE_LIST", "yeah,ok,hmm,uh-huh,right,uh huh")
raw_interrupt = os.getenv("INTERRUPT_WORDS", "stop,wait,no,hold,pause")
raw_start = os.getenv("INTERRUPT_START_WORDS", "start,hello,hi")

_IGNORE = _parse(raw_ignore)
_INTERRUPT = _parse(raw_interrupt)
_START = _parse(raw_start)

def _split(items: Iterable[str]):
    words = {w for w in items if " " not in w}
    phrases = {p for p in items if " " in p}
    return words, phrases

IGNORE_WORDS, IGNORE_PHRASES = _split(_IGNORE)
INTERRUPT_WORDS, INTERRUPT_PHRASES = _split(_INTERRUPT)
START_WORDS, START_PHRASES = _split(_START)

def normalize(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    t = t.replace("-", " ")
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

# decision modes:
# - "RESPOND_ONCE": agent should speak once and then stop
# - "RESPOND_CONTINUE": agent should speak and remain speaking until interrupted
# - "IGNORE": do nothing (agent keeps doing what it was doing)
# - "INTERRUPT": stop speaking immediately
async def decide_action(
    transcript: str,
    agent_is_speaking: bool,
    was_speaking_recently: bool = False,
) -> dict:
    """
    Return a dict with:
      - decision: one of "RESPOND", "IGNORE", "INTERRUPT"
      - mode: either "once" or "continue" (only relevant for RESPOND)
      - reason: human-friendly reason
    """
    t = normalize(transcript)
    tokens = t.split()

    # --- If the agent is speaking right now ---
    if agent_is_speaking:
        # check interrupt phrases (multi-word)
        for phrase in INTERRUPT_PHRASES:
            if phrase and phrase in t:
                return {"decision": "INTERRUPT", "mode": None, "reason": "found interrupt phrase"}

        # check interrupt tokens
        if any(tok in INTERRUPT_WORDS for tok in tokens):
            return {"decision": "INTERRUPT", "mode": None, "reason": "found interrupt word"}

        # if all tokens are ignore words => IGNORE
        if tokens and all(tok in IGNORE_WORDS for tok in tokens):
            return {"decision": "IGNORE", "mode": None, "reason": "pure ignore words while speaking"}

        # check ignore phrases
        for phrase in IGNORE_PHRASES:
            if phrase and phrase in t:
                return {"decision": "IGNORE", "mode": None, "reason": "ignore phrase while speaking"}

        # default while speaking: ignore (no interrupt detected)
        return {"decision": "IGNORE", "mode": None, "reason": "default ignore while speaking"}

    # --- Agent is silent ---
    # Two subcases: recently spoken vs not recently spoken

    if was_speaking_recently:
        # If user only said an ignore/backchannel -> respond and CONTINUE speaking
        if tokens and all(tok in IGNORE_WORDS for tok in tokens):
            return {"decision": "RESPOND", "mode": "continue", "reason": "recently spoke; user gave backchannel -> respond and continue speaking"}

        for phrase in IGNORE_PHRASES:
            if phrase and phrase in t:
                return {"decision": "RESPOND", "mode": "continue", "reason": "recently spoke; ignore phrase -> respond and continue speaking"}

        # Otherwise respond once (default)
        return {"decision": "RESPOND", "mode": "once", "reason": "recently spoke; non-backchannel input -> respond once"}

    else:
        # Agent silent and hasn't spoken recently
        # If user says start/hello -> respond once
        for phrase in START_PHRASES:
            if phrase and phrase in t:
                return {"decision": "RESPOND", "mode": "once", "reason": "start/hello while silent -> respond once"}

        if any(tok in START_WORDS for tok in tokens):
            return {"decision": "RESPOND", "mode": "once", "reason": "start word while silent -> respond once"}

        # Default: respond once to any user input while silent
        return {"decision": "RESPOND", "mode": "once", "reason": "agent silent & no recent speech -> respond once"}


async def enqueue_potential_interrupt(
    get_transcript,
    agent_is_speaking: bool,
    on_interrupt,
    on_ignore,
    *,
    timeout_ms: int = 150,
    logger: Optional[Callable[[str, str, str], None]] = None,
    was_speaking_recently: bool = False,
):
    """
    Wait for an STT transcript (via get_transcript) up to timeout_ms (ms).
    Decide via decide_action and call callbacks:
      - If decision == INTERRUPT: call on_interrupt()  (stops current speech)
      - If decision == IGNORE: call on_ignore()
      - If decision == RESPOND:
          * if mode == "continue": call on_interrupt() (treat like interrupt-callback that will start continuous speaking)
          * if mode == "once": call on_interrupt() (treat as start reply once)
    Note: callbacks must handle semantics depending on agent state (they get invoked for both interrupt & respond)
    """
    if logger is None:
        logger = lambda transcript, decision, reason: None

    try:
        transcript = await asyncio.wait_for(get_transcript(), timeout=timeout_ms / 1000)
    except asyncio.TimeoutError:
        # STT timed out: if speaking -> IGNORE; if silent -> RESPOND_ONCE (safe default)
        if agent_is_speaking:
            decision = {"decision": "IGNORE", "mode": None, "reason": "stt_timeout_while_speaking"}
            logger("", decision["decision"], decision["reason"])
            try:
                await on_ignore()
            except Exception:
                pass
            return decision
        else:
            decision = {"decision": "RESPOND", "mode": "once", "reason": "stt_timeout_while_silent"}
            logger("", decision["decision"], decision["reason"])
            try:
                await on_interrupt()  # call on_interrupt style to start the reply
            except Exception:
                pass
            return decision
    except Exception as e:
        decision = {"decision": "IGNORE", "mode": None, "reason": f"stt_error:{e}"}
        logger("", decision["decision"], decision["reason"])
        try:
            await on_ignore()
        except Exception:
            pass
        return decision

    # Normal case: we got a transcript
    decision = await decide_action(transcript, agent_is_speaking, was_speaking_recently)
    logger(transcript, decision["decision"], decision["reason"])

    # Callbacks: on_interrupt used generically to start a response or stop speech.
    try:
        if decision["decision"] == "INTERRUPT":
            await on_interrupt()
        elif decision["decision"] == "IGNORE":
            await on_ignore()
        else:  # RESPOND
            # call on_interrupt-style callback to trigger your respond flow.
            # The callback should inspect agent state / mode and act:
            # - if mode == "continue": start speaking and remain speaking until stopped
            # - if mode == "once": speak one reply and then stop
            await on_interrupt()
    except Exception:
        # swallow errors in user callbacks so handler remains stable
        pass

    # return the full decision to caller so they can act explicitly if they want
    return decision