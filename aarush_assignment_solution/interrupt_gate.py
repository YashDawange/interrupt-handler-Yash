# interrupt_gate.py

import asyncio
import time
from typing import Optional

from config import (
    INTERRUPT_WORDS,
    PASSIVE_WORDS,
    INTERRUPT_WORD_WEIGHT,
    PASSIVE_WORD_WEIGHT,
    INTERRUPT_DECISION_TIMEOUT,
)


class InterruptGate:
    """
    Context-aware interruption gate using interrupt score logic.
    """

    def __init__(self):
        self.agent_is_speaking: bool = False

        self._pending: bool = False
        self._pending_since: Optional[float] = None

        self._latest_transcript: Optional[str] = None
        self._decision_event = asyncio.Event()

    # ---------- agent state ----------

    def on_agent_speaking_start(self):
        self.agent_is_speaking = True

    def on_agent_speaking_end(self):
        self.agent_is_speaking = False
        self._reset()

    # ---------- vad ----------

    def on_vad_detected(self):
        if not self.agent_is_speaking:
            return

        self._pending = True
        self._pending_since = time.monotonic()
        self._decision_event.clear()

        print("[Gate] VAD detected → tentative interruption")

    # ---------- stt ----------

    def on_stt_text(self, text: str):
        if not self._pending:
            return

        self._latest_transcript = text.lower().strip()
        self._decision_event.set()

    # ---------- decision ----------

    async def should_interrupt(self) -> bool:
        if not self._pending:
            return False

        try:
            await asyncio.wait_for(
                self._decision_event.wait(),
                timeout=INTERRUPT_DECISION_TIMEOUT,
            )
        except asyncio.TimeoutError:
            print("[Gate] STT timeout → ignore")
            self._reset()
            return False

        transcript = self._latest_transcript or ""
        score = self._compute_score(transcript)

        print(f"[Gate] transcript='{transcript}' | score={score}")

        self._reset()
        return score > 0

    # ---------- scoring ----------

    def _compute_score(self, transcript: str) -> float:
        score = 0.0
        tokens = transcript.split()

        for token in tokens:
            if token in INTERRUPT_WORDS:
                score += INTERRUPT_WORD_WEIGHT
            elif token in PASSIVE_WORDS:
                score += PASSIVE_WORD_WEIGHT

        return score

    # ---------- internal ----------

    def _reset(self):
        self._pending = False
        self._pending_since = None
        self._latest_transcript = None
        self._decision_event.clear()
