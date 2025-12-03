import os
import re
import asyncio
from typing import Set

try:
    from livekit.agents import AgentSession, UserInputTranscribedEvent, SpeechCreatedEvent, AgentStateChangedEvent, UserStateChangedEvent
except Exception:
    AgentSession = object
    UserInputTranscribedEvent = object
    SpeechCreatedEvent = object
    AgentStateChangedEvent = object
    UserStateChangedEvent = object

DEFAULT_IGNORE = ["yeah", "ok", "okay", "hmm", "uh-huh", "right", "mm", "mm-hm"]
DEFAULT_INTERRUPT_WORDS = ["stop", "wait", "no", "hold", "please", "pause", "please stop"]
STT_DEBOUNCE = float(os.getenv("STT_DEBOUNCE", "0.45"))

def load_ignore_set() -> Set[str]:
    val = os.getenv("IGNORE_WORDS")
    if not val:
        return set(DEFAULT_IGNORE)
    return set(w.strip().lower() for w in val.split(",") if w.strip())

def load_interrupt_set() -> Set[str]:
    val = os.getenv("INTERRUPT_WORDS")
    if not val:
        return set(DEFAULT_INTERRUPT_WORDS)
    return set(w.strip().lower() for w in val.split(",") if w.strip())

IGNORE_WORDS = load_ignore_set()
INTERRUPT_WORDS = load_interrupt_set()

_word_split_re = re.compile(r"[^\w']+")

def tokenize(text: str):
    return [t.lower() for t in _word_split_re.split(text) if t.strip()]

class InterruptHandler:
    def __init__(self, session: AgentSession):
        self.session = session
        self.speaking = False
        self._pending_debounce: asyncio.Task | None = None
        self._last_transcript: str | None = None

        # register handlers (works if session exposes .on)
        try:
            session.on("speech_created")(self._on_speech_created)
            session.on("agent_state_changed")(self._on_agent_state_changed)
            session.on("user_state_changed")(self._on_user_state_changed)
            session.on("user_input_transcribed")(self._on_user_input_transcribed)
        except Exception:
            # If session API differs, user will need to wire handlers manually
            self._log("warning: automatic event registration failed; you must attach handlers manually.")

    def _log(self, *args):
        print("[InterruptHandler]", *args)

    def _on_speech_created(self, event: SpeechCreatedEvent):
        self.speaking = True
        self._log("speech_created -> speaking=True")
        handle = getattr(event, "speech_handle", None)
        if handle:
            async def wait_end():
                try:
                    await handle.wait_for_playout()
                except Exception:
                    pass
                self.speaking = False
                self._log("speech finished -> speaking=False")
            asyncio.create_task(wait_end())

    def _on_agent_state_changed(self, event: AgentStateChangedEvent):
        new = getattr(event, "new_state", None)
        name = getattr(new, "name", None)
        if name == "speaking":
            self.speaking = True
            self._log("agent_state_changed -> speaking=True")
        elif name in ("listening", "thinking", "initializing", None):
            self.speaking = False
            self._log(f"agent_state_changed -> speaking=False (state={name})")

    def _on_user_state_changed(self, event: UserStateChangedEvent):
        new = getattr(event, "new_state", None)
        name = getattr(new, "name", "")
        self._log("user_state_changed", name)
        if self.speaking and name == "speaking":
            if self._pending_debounce and not self._pending_debounce.done():
                self._pending_debounce.cancel()
            self._pending_debounce = asyncio.create_task(self._debounce_then_check())

    async def _debounce_then_check(self):
        await asyncio.sleep(STT_DEBOUNCE)
        transcript = self._last_transcript or ""
        self._log("debounce check transcript:", repr(transcript))
        if not transcript:
            self._log("no transcript after debounce -> IGNORE")
            return
        toks = tokenize(transcript)
        if not toks:
            self._log("empty token list -> IGNORE")
            return
        if any(t in INTERRUPT_WORDS for t in toks):
            self._log("interrupt word detected in transcript -> INTERRUPT now")
            try:
                await self.session.interrupt(force=True)
            except Exception as e:
                self._log("error calling session.interrupt:", e)
            return
        if all(t in IGNORE_WORDS for t in toks):
            self._log("transcript contains only ignore/backchannel tokens -> IGNORE")
            return
        self._log("transcript is mixed/other content -> INTERRUPT")
        try:
            await self.session.interrupt(force=True)
        except Exception as e:
            self._log("error calling session.interrupt:", e)

    def _on_user_input_transcribed(self, event: UserInputTranscribedEvent):
        text = getattr(event, "transcript", "") or ""
        is_final = getattr(event, "is_final", False)
        self._log("user_input_transcribed:", repr(text), "final:", is_final)
        if text:
            self._last_transcript = text
        if not self.speaking and is_final:
            self._log("agent not speaking -> normal processing")
            return
        if self.speaking and is_final:
            toks = tokenize(text)
            if not toks:
                self._log("final transcript empty -> IGNORE")
                return
            if any(t in INTERRUPT_WORDS for t in toks):
                self._log("final transcript contains interrupt -> INTERRUPT")
                asyncio.create_task(self.session.interrupt(force=True))
                return
            if all(t in IGNORE_WORDS for t in toks):
                self._log("final transcript only ignore tokens -> IGNORE")
                return
            self._log("final transcript mixed -> INTERRUPT")
            asyncio.create_task(self.session.interrupt(force=True))
