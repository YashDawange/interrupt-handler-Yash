# livekit-agents/voice/interrupt_handler.py
from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Iterable, Optional

# Default lists (tweak as needed)
DEFAULT_SOFT_IGNORE = ["yeah", "ok", "okay", "hmm", "uh-huh", "yep", "right"]
DEFAULT_HARD = ["wait", "stop", "no", "pause", "hold", "listen", "actually", "hang", "cancel"]

# Small helper to normalize transcripts
def _normalize(text: str) -> str:
    t = (text or "").lower().strip()
    # remove punctuation except mid-word apostrophes/hyphens
    t = re.sub(r"[^\w\s'-]", "", t)
    return t


class InterruptHandler:
    """
    Integrates with AudioRecognition / AgentSession.

    Usage:
      - Construct with (session, *, ignore_list=None, hard_list=None, timeout=0.28)
      - Call .on_vad_start(ev) from the VAD START_OF_SPEECH branch.
      - Call .on_stt_partial(text) from the STT PREFLIGHT/INTERIM branch.
      - Call .on_stt_final(text) from the STT FINAL branch (optional).
    """

    def __init__(
        self,
        session,
        *,
        ignore_list: Optional[Iterable[str]] = None,
        hard_list: Optional[Iterable[str]] = None,
        partial_timeout: float | None = None,
    ):
        self._session = session
        self._ignore = set([t.lower() for t in (ignore_list or DEFAULT_SOFT_IGNORE)])
        self._hard = set([t.lower() for t in (hard_list or DEFAULT_HARD)])
        # partial timeout fallback: use session option false_interruption_timeout if provided
        if partial_timeout is None:
            partial_timeout = getattr(session.options, "false_interruption_timeout", 0.28) or 0.28
        self._timeout = float(partial_timeout)

        # load from env if provided (comma-separated)
        env_soft = os.getenv("SOFT_IGNORE_LIST")
        if env_soft:
            self._ignore = set([t.strip().lower() for t in env_soft.split(",") if t.strip()])

        env_hard = os.getenv("HARD_COMMAND_LIST")
        if env_hard:
            self._hard = set([t.strip().lower() for t in env_hard.split(",") if t.strip()])

        # pending structure keyed by user (can be extended to multi-user)
        # value: dict with keys { "since":float, "timer":asyncio.Task|None, "last_text": str|None }
        self._pending: dict[str, dict] = {}

        # small lock to avoid races
        self._lock = asyncio.Lock()

    async def on_vad_start(self, ev) -> None:
        """
        Called when VAD emits START_OF_SPEECH.
        ev is the VADEvent object (we only need speaker id if available).
        """
        # determine speaker id if present; fallback to single-global key
        user_id = getattr(ev, "speaker_id", "default")
        # If agent not speaking -> we should not ignore. Let the normal AudioRecognition pipeline handle it.
        if not self._session or self._session.agent_state != "speaking":
            # No special handling required while agent is silent
            return

        # If already pending, we don't start another timer
        async with self._lock:
            if user_id in self._pending:
                return

            # create pending entry and start a timeout task
            entry = {"since": time.time(), "last_text": None, "timer": None}
            self._pending[user_id] = entry

            # start a timer that will clear the pending if no partial arrives
            entry["timer"] = asyncio.create_task(self._pending_timeout(user_id))

    async def _pending_timeout(self, user_id: str) -> None:
        # wait for short timeout, if no transcript -> treat as soft/ignore (do nothing)
        try:
            await asyncio.sleep(self._timeout)
        except asyncio.CancelledError:
            return
        async with self._lock:
            # if still pending and no text, clear and ignore (do nothing)
            if user_id in self._pending:
                self._pending.pop(user_id, None)

    async def on_stt_partial(self, ev_text: str, *, speaker_id: Optional[str] = None) -> None:
        """
        Called for PREFLIGHT or INTERIM transcripts (fast partials).
        ev_text: partial transcript text.
        If the agent was speaking and we have a pending VAD event for this speaker,
        we decide whether to interrupt or ignore based on tokens.
        """
        if not ev_text:
            return
        user_id = speaker_id or "default"
        text = _normalize(ev_text)

        # Fast path: if agent not speaking -> nothing to special-handle here.
        if self._session.agent_state != "speaking":
            return

        async with self._lock:
            if user_id not in self._pending:
                # no VAD transient pending -> nothing to do
                return

            # cancel the pending timeout (we received a partial)
            timer = self._pending[user_id].get("timer")
            if timer and not timer.done():
                timer.cancel()

            self._pending[user_id]["last_text"] = text

            # Decide: if text contains any hard token -> interrupt
            tokens = [t for t in text.split() if t]
            if any(tok in self._hard for tok in tokens):
                # interrupt
                # We call session.interrupt() (it returns a future)
                try:
                    # call interrupt; schedule it to avoid blocking the STT handler for long
                    fut = self._session.interrupt()
                    # feed transcript into normal handle: commit or dispatch the transcript if desired
                    # Some sessions expect STT events later; but it's fine to attempt to pass the text
                    # to the session so it knows what caused interrupt.
                    if hasattr(self._session, "_activity") and self._session._activity:
                        # if the Activity exposes a handler for incoming user text, call it
                        handle_text = getattr(self._session._activity, "handle_incoming_user_text", None)
                        if callable(handle_text):
                            # schedule async call but don't await if not necessary
                            asyncio.create_task(handle_text(text))
                    # make sure interrupt future is awaited (not required here)
                    return
                finally:
                    self._pending.pop(user_id, None)

            # If there exists any token that's not in soft-ignore -> interrupt
            non_soft = [tok for tok in tokens if tok not in self._ignore]
            if non_soft:
                # mixed phrase "yeah wait" -> trigger interrupt
                try:
                    fut = self._session.interrupt()
                    # optionally deliver the partial text to activity as above
                    if hasattr(self._session, "_activity") and self._session._activity:
                        handle_text = getattr(self._session._activity, "handle_incoming_user_text", None)
                        if callable(handle_text):
                            asyncio.create_task(handle_text(text))
                    return
                finally:
                    self._pending.pop(user_id, None)

            # Otherwise: all tokens are soft -> do nothing (ignore)
            self._pending.pop(user_id, None)
            return

    async def on_stt_final(self, ev_text: str, *, speaker_id: Optional[str] = None) -> None:
        """
        Called for FINAL transcripts. If a VAD pending existed we evaluate the same logic again
        just in case final text adds command tokens.
        """
        if not ev_text:
            return
        user_id = speaker_id or "default"
        text = _normalize(ev_text)

        # If agent not speaking just return; final is processed normally elsewhere
        if self._session.agent_state != "speaking":
            return

        async with self._lock:
            if user_id not in self._pending:
                return

            # same decision rules as partial
            tokens = [t for t in text.split() if t]
            if any(tok in self._hard for tok in tokens) or any(tok not in self._ignore for tok in tokens):
                # interrupt
                try:
                    fut = self._session.interrupt()
                    if hasattr(self._session, "_activity") and self._session._activity:
                        handle_text = getattr(self._session._activity, "handle_incoming_user_text", None)
                        if callable(handle_text):
                            asyncio.create_task(handle_text(text))
                    return
                finally:
                    self._pending.pop(user_id, None)

            # otherwise ignore
            self._pending.pop(user_id, None)
