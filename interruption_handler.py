
import os
import re
from typing import Set

from livekit.agents import (
    UserInputTranscribedEvent,
    AgentSession,
    AgentStateChangedEvent,
)


# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

def _load_word_set(env_name: str, default: str) -> Set[str]:
    raw = os.getenv(env_name, default)
    return {w.strip().lower() for w in raw.split(",") if w.strip()}


def _normalize(text: str) -> str:
    """Lowercase, remove symbols, compress spaces."""
    text = re.sub(r"[^a-zA-Z\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


# -----------------------------------------------------------
# Backchannel + Interrupt Phrase Dictionaries
# -----------------------------------------------------------

BACKCHANNEL_WORDS: Set[str] = _load_word_set(
    "BACKCHANNEL_WORDS",
    "yeah, ok, okay, aha, hmm, mhm, uh-huh, uh huh, yup, yep, right, "
    "mmm, uh, um, er, ah, oh, huh, yes, yea, cool, nice, great, good, "
    "alright, fine"
)

INTERRUPT_PHRASES: Set[str] = _load_word_set(
    "INTERRUPT_WORDS",
    "stop, wait, hold on, hang on, pause, no, one sec, one second, "
    "sorry, excuse me, but, actually, however"
)


def _is_backchannel(norm: str) -> bool:
    if not norm:
        return False
    tokens = norm.split()
    return all(t in BACKCHANNEL_WORDS for t in tokens)


def _is_explicit_interrupt(norm: str) -> bool:
    if not norm:
        return False
    for phrase in INTERRUPT_PHRASES:
        if phrase in norm:
            return True
    return False


# -----------------------------------------------------------
# MAIN INSTALLER — Matching the first script's logic
# -----------------------------------------------------------

def install_interruption_handler(session: AgentSession):
    """
    Pure, clean interruption logic (same as first code):
    - If agent is speaking:
        - Explicit interrupt phrase → session.interrupt()
        - Pure backchannel → ignore + clear_user_turn()
        - Multi-word utterance → interrupt
        - Single unknown word → ignore
    - If agent not speaking → normal LiveKit behavior
    """

    state = {"agent_speaking": False}

    # Track whether agent is speaking from LiveKit callbacks
    @session.on("agent_state_changed")
    def _on_state(event: AgentStateChangedEvent):
        state["agent_speaking"] = (event.new_state == "speaking")

    # Main logic
    @session.on("user_input_transcribed")
    def _on_user(event: UserInputTranscribedEvent):
        if not event.is_final:
            return

        raw = (event.transcript or "").strip()
        norm = _normalize(raw)
        if not norm:
            return

        # If agent is silent → let LiveKit handle normally
        if not state["agent_speaking"]:
            print(f"[InterruptHandler] Agent silent → passing through: {raw!r}")
            return

        # -----------------------------
        # Agent IS speaking — apply filtering
        # -----------------------------

        # Priority 1 — explicit interrupt phrase
        if _is_explicit_interrupt(norm):
            print(f"[InterruptHandler] EXPLICIT INTERRUPT → {raw!r}")
            session.interrupt()
            session.clear_user_turn()
            return

        # Priority 2 — pure backchannel
        if _is_backchannel(norm):
            print(f"[InterruptHandler] BACKCHANNEL IGNORED → {raw!r}")
            session.clear_user_turn()
            return

        # Priority 3 — multi-word utterance (real interrupt)
        tokens = norm.split()
        if len(tokens) >= 2:
            print(f"[InterruptHandler] REAL USER INTERRUPTION → {raw!r}")
            session.interrupt()
            return

        # Priority 4 — single word, not a backchannel
        print(f"[InterruptHandler] SINGLE-WORD IGNORED → {raw!r}")
        # do not interrupt, do not clear (safer)
        return


