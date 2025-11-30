import os
import re
from typing import Set

from livekit.agents import (
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
    AgentSession,
)

# ---------- helpers for word sets ---------- #

def _load_token_set(env_name: str, default: str) -> Set[str]:
    """
    Load a comma-separated list from env, fall back to default.
    All normalized to lowercase and stripped.
    """
    raw = os.getenv(env_name, default)
    return {
        w.strip().lower()
        for w in raw.split(",")
        if w.strip()
    }


PASSIVE_ACKS: Set[str] = _load_token_set(
    "BACKCHANNEL_WORDS",
    "yeah, ok, okay, aha, hmm, mm-hmm, mm hmm, uh-huh, uh huh, "
    "yep, yup, right, mmm, mhm, uhuh",
)

HALT_PHRASES: Set[str] = _load_token_set(
    "INTERRUPT_WORDS",
    "stop, wait, hold on, hang on, pause, one second, one sec",
)


def _canonicalize(text: str) -> str:
    """Lowercase and strip to letters/spaces/apostrophes."""
    text = re.sub(r"[^a-zA-Z\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _is_passive_ack(norm_text: str) -> bool:
    if not norm_text:
        return False
    parts = norm_text.split()
    # treat as backchannel if *all* tokens are in the set
    return all(tok in PASSIVE_ACKS for tok in parts)


def _contains_interrupt(norm_text: str) -> bool:
    if not norm_text:
        return False
    for phrase in HALT_PHRASES:
        if phrase and phrase in norm_text:
            return True
    return False


# ---------- main installer ---------- #

def attach_interruption_filter(session: AgentSession) -> None:
    """
    Adds intelligent interruption behavior to the given session.

    While agent is speaking:
      - 'stop' / 'wait' / 'hold on' --> session.interrupt()
      - 'yeah' / 'ok' / 'hmm' ...   --> ignored (no new turn, no stop)
      - longer utterances           --> treated as a real interruption

    While agent is NOT speaking:
      - input is left untouched; the normal pipeline handles it.
    """

    state = {"is_speaking": False}

    @session.on("agent_state_changed")
    def _evt_agent_state(event: AgentStateChangedEvent) -> None:
        state["is_speaking"] = (event.new_state == "speaking")

    @session.on("user_input_transcribed")
    def _evt_user_stt(event: UserInputTranscribedEvent) -> None:
        # only care about final transcripts
        if not event.is_final:
            return

        utter_raw = (event.transcript or "").strip()
        utter_norm = _canonicalize(utter_raw)
        if not utter_norm:
            return

        if not state["is_speaking"]:
            # agent is silent -> let LiveKit handle normally
            return

        # agent is currently speaking

        # 1) explicit interrupt phrases
        if _contains_interrupt(utter_norm):
            print(f"[interrupt_handler] explicit interrupt: {utter_norm!r}")
            session.interrupt()
            session.clear_user_turn()
            return

        # 2) pure backchannel / filler
        if _is_passive_ack(utter_norm):
            print(f"[interrupt_handler] backchannel ignored: {utter_norm!r}")
            # do NOT interrupt, and clear this as a user turn so it doesn't
            # pollute conversation history
            session.clear_user_turn()
            return

        # 3) other mid-speech user input
        parts = utter_norm.split()
        if len(parts) >= 2:
            # consider this a genuine "actually I want to say something" interrupt
            print(f"[interrupt_handler] real mid-speech interrupt: {utter_norm!r}")
            session.interrupt()
            # the content will be processed as a normal user message
            return

        # if it's a single weird token that isn't in backchannel or interrupt,
        # we'll just ignore it (no interrupt, no clear)
        print(f"[interrupt_handler] ignored single token while speaking: {utter_norm!r}")


# Back-compat export so existing imports keep working
def install_interruption_handler(session: AgentSession) -> None:
    attach_interruption_filter(session)
