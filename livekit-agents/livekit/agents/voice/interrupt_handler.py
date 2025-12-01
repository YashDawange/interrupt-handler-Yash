import asyncio
import re

IGNORE_WORDS = [
    "yeah", "ok", "okay", "hmm", "uh-huh", "uh huh", "uhuh",
    "right", "mm", "mm-hm", "mhm"
]

INTERRUPT_WORDS = [
    "stop", "wait", "hold on", "no", "stop that",
    "wait a second", "wait please", "cut", "pause"
]

WORD_RE = re.compile(r"[A-Za-z0-9']+")


def tokenize_text(text: str):
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def contains_interrupt_word(text: str) -> bool:
    t = text.lower()
    for w in INTERRUPT_WORDS:
        if w in t:
            return True
    return False


class InterruptHandler:
    """
    Final simplified interrupt handler.
    Implements ONLY what the assignment requires:

      ✔ Agent speaking + interrupt words → interrupt
      ✔ Agent speaking + ignore words → ignore
      ✔ Agent speaking + mixed → interrupt
      ✔ Agent silent → always treat as user input
      ✔ VAD start while agent speaking → treat_as_user_turn
      ✔ _do_interrupt is overridden by AgentSession
    """

    def __init__(self, get_agent_state_callable):
        self.get_agent_state = get_agent_state_callable
        self._lock = asyncio.Lock()

    async def _maybe_call_get_agent_state(self) -> bool:
        res = self.get_agent_state()
        if asyncio.iscoroutine(res):
            res = await res
        return bool(res)

    # ---------------------------------------------
    # VAD HOOK
    # ---------------------------------------------
    async def on_vad_start(self, session_id: str):
        agent_speaking = await self._maybe_call_get_agent_state()

        if agent_speaking:
            # user talked while agent speaking → immediate interruption
            return {
                "action": "treat_as_user_turn",
                "reason": "agent_silent_on_vad",
            }

        return {"action": "deferred"}

    # ---------------------------------------------
    # STT HOOK
    # ---------------------------------------------
    async def on_transcript(self, session_id: str, transcript: str, is_final: bool = True):

        agent_speaking = await self._maybe_call_get_agent_state()
        tokens = tokenize_text(transcript)

        # Agent silent → ALWAYS treat as user text
        if not agent_speaking:
            return {
                "action": "user_input",
                "transcript": transcript,
                "reason": "agent_silent",
            }

        # semantic interrupt always wins
        if contains_interrupt_word(transcript):
            await self._do_interrupt(session_id, transcript, reason="semantic_interrupt")
            return {
                "action": "interrupt",
                "transcript": transcript,
                "reason": "semantic_interrupt",
            }

        # evaluate backchannel / mixed tokens
        decision = self._decide_from_tokens(tokens)

        if decision == "interrupt":
            await self._do_interrupt(session_id, transcript, reason="transcript_trigger")
            return {
                "action": "interrupt",
                "transcript": transcript,
            }

        return {
            "action": "ignore",
            "transcript": transcript,
            "reason": "backchannel_while_speaking",
        }

    # ---------------------------------------------
    # Decision logic
    # ---------------------------------------------
    def _decide_from_tokens(self, tokens):

        if not tokens:
            return "ignore"

        low = [t.lower() for t in tokens]

        # all tokens are ignore words
        if all(tok in IGNORE_WORDS for tok in low):
            return "ignore"

        return "interrupt"

    # ---------------------------------------------
    # Overridden by AgentSession
    # ---------------------------------------------
    async def _do_interrupt(self, session_id: str, transcript: str = "", reason: str = ""):
        pass
