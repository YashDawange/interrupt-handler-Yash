# interrupt_handler.py
"""
Robust InterruptHandler for voice agents.

Provides:
 - InterruptHandler(session)  # construct with session-like object
 - .start()        # non-blocking; preferred for callers that expect a sync start
 - .start_async()  # async entrypoint (awaitable)
 - .run()          # blocking entrypoint for manual runs (runs start_async())
 - .stop()         # unbind events and cancel pending tasks

Session requirements (best-effort):
 - session.on(event_name, callback) to subscribe
 - session.off(event_name, callback) to unsubscribe (optional)
 - adapter will attempt to call session.stop() / stop_audio() / stop_tts() to halt agent output
 - adapter will attempt to call session.handle_recognized_user_text(...) or similar to push recognized text
"""
import asyncio
import os
import time
import re
import threading
import traceback
from typing import Optional, Callable, Any, Dict, List

# Config (env override)
IGNORE_WORDS = [w.strip().lower() for w in (os.getenv("IGNORE_WORDS") or
    "yeah,yep,yup,ya,yea,yeahh,okay,ok,uh-huh,uhh,uhm,um,ah,aha,mm,mmh,mhm,mhmm,mmh,alright,right,gotcha,roger,indeed,sure,nah"
).split(",") if w.strip()]

INTERRUPT_WORDS = [w.strip().lower() for w in (os.getenv("INTERRUPT_WORDS") or
    "stop,wait,hold,hold on,no,pause,cancel,actually,excuse me,now,stop now,wait now"
).split(",") if w.strip()]

STT_DEBOUNCE_MS = int(os.getenv("STT_DEBOUNCE_MS") or "300")
STT_MAX_WAIT_MS = int(os.getenv("STT_MAX_WAIT_MS") or "450")
LOG = os.getenv("INTERRUPT_HANDLER_LOG", "0") == "1"

def _log(*args):
    if LOG:
        print("[interrupt_handler]", *args)

def tokenize_transcript(text: str) -> List[str]:
    if not text:
        return []
    t = text.lower().strip()
    # keep apostrophes and hyphens; replace others with spaces
    t = re.sub(r"[^\w'\-]", " ", t)
    tokens = [tok for tok in t.split() if tok]
    # small normalization
    tokens = [tok.replace("okay", "ok") for tok in tokens]
    return tokens

class SessionAdapter:
    """Adapter that abstracts common session operations in a tolerant way."""
    def __init__(self, session: Any):
        self.session = session
        self._speaking = False
        self._last_stop_ts = 0.0
        self._grace_ms = int(os.getenv("SPEAKING_GRACE_MS") or "200")
        # try to subscribe to common tts/audio events if available
        on = getattr(self.session, "on", None)
        if callable(on):
            for ev in ("tts:start", "tts:started", "tts:play", "audio:playback:start", "audio:started", "playback:start"):
                try:
                    on(ev, self._on_speech_start)
                except Exception:
                    pass
            for ev in ("tts:stop", "tts:finished", "tts:ended", "audio:playback:stop", "audio:finished", "playback:stop"):
                try:
                    on(ev, self._on_speech_stop)
                except Exception:
                    pass

    def _on_speech_start(self, _meta=None):
        self._speaking = True
        _log("SessionAdapter: speech start")

    def _on_speech_stop(self, _meta=None):
        self._speaking = False
        self._last_stop_ts = time.time()
        _log("SessionAdapter: speech stop")

    def is_speaking(self) -> bool:
        if self._speaking:
            return True
        if (time.time() - self._last_stop_ts) * 1000.0 < self._grace_ms:
            _log("SessionAdapter: within grace window -> speaking")
            return True
        if getattr(self.session, "is_playing_audio", False) or getattr(self.session, "playing_audio", False):
            _log("SessionAdapter: fallback attribute -> speaking")
            return True
        if getattr(self.session, "is_generating", False) or getattr(self.session, "tts_running", False):
            _log("SessionAdapter: generating flag -> speaking")
            return True
        return False

    async def stop_agent_audio(self):
        stop_fn = getattr(self.session, "stop", None) or getattr(self.session, "stop_audio", None) or getattr(self.session, "stop_tts", None)
        if stop_fn:
            try:
                res = stop_fn()
                if asyncio.iscoroutine(res):
                    await res
                _log("stop_agent_audio called")
            except Exception:
                _log("stop_agent_audio raised:", traceback.format_exc())
        else:
            _log("stop_agent_audio: no stop function found")

    def continue_agent_audio(self):
        _log("continue_agent_audio called (no-op)")

    def emit_user_input_event(self, text: str):
        push_fn = getattr(self.session, "handle_recognized_user_text", None) or getattr(self.session, "process_user_text", None) or getattr(self.session, "on_user_text", None) or getattr(self.session, "receive_user_text", None)
        if push_fn:
            try:
                res = push_fn(text)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                _log("emit_user_input_event: pushed text")
            except Exception:
                _log("emit_user_input_event error:", traceback.format_exc())
        else:
            _log("emit_user_input_event: no push function found; text:", text)

class PendingVad:
    def __init__(self, vad_id: str):
        self.vad_id = vad_id
        self.transcripts: List[str] = []
        self._task: Optional[asyncio.Task] = None
        self._done = False

    def append(self, text: str):
        if text:
            self.transcripts.append(text)

    def combined(self) -> str:
        return " ".join(self.transcripts).strip().lower()

    def cancel(self):
        self._done = True
        if self._task and not self._task.done():
            self._task.cancel()

class InterruptHandler:
    def __init__(self, session: Any):
        self.session = session
        self.adapter = SessionAdapter(session)
        self.pending: Dict[str, PendingVad] = {}
        self._bound = False
        self._lock = threading.Lock()
        self._background_tasks: List[asyncio.Task] = []

    # --- binding helpers ---
    def _bind_event(self, name: str, handler: Callable):
        on = getattr(self.session, "on", None)
        if callable(on):
            try:
                on(name, handler)
                _log("bound", name)
                return True
            except Exception:
                _log(f"failed to bind {name}")
        return False

    def _unbind_event(self, name: str, handler: Callable):
        off = getattr(self.session, "off", None)
        if callable(off):
            try:
                off(name, handler)
                _log("unbound", name)
            except Exception:
                pass

    # --- public lifecycle ---
    def start(self):
        """Non-blocking start - preferred for callers expecting a sync start."""
        # if already bound, noop
        if self._bound:
            return
        # call start_async in background to be safe whether loop exists or not
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # schedule async start on running loop
                asyncio.create_task(self.start_async())
            else:
                # start a loop in a background thread to run start_async
                threading.Thread(target=lambda: asyncio.run(self.start_async()), daemon=True).start()
            _log("start(): scheduled start_async")
        except RuntimeError:
            # no current loop object; run in background thread
            threading.Thread(target=lambda: asyncio.run(self.start_async()), daemon=True).start()
            _log("start(): launched background thread for start_async")

    async def start_async(self):
        """Async-aware start routine - binds to session events."""
        with self._lock:
            if self._bound:
                return
            # try to bind common events; don't fail if some are missing
            self._bind_event("vad:start", self._on_vad_start)
            self._bind_event("vad:stop", self._on_vad_stop)
            self._bind_event("stt:partial", self._on_stt_partial)
            self._bind_event("stt:final", self._on_stt_final)
            self._bound = True
            _log("start_async: bound to session events")

    def run(self):
        """Blocking run entrypoint (useful for manual testing)."""
        try:
            asyncio.run(self.start_async())
            # keep running until stop() is called; this is minimal — the real agent typically controls lifecycle
            while self._bound:
                time.sleep(0.1)
        except KeyboardInterrupt:
            _log("run: interrupted by keyboard")
        except Exception:
            _log("run: exception:\n", traceback.format_exc())
        finally:
            self.stop()

    def stop(self):
        """Unbind events and cancel pending tasks."""
        with self._lock:
            if not self._bound:
                return
            # unbind events where possible
            self._unbind_event("vad:start", self._on_vad_start)
            self._unbind_event("vad:stop", self._on_vad_stop)
            self._unbind_event("stt:partial", self._on_stt_partial)
            self._unbind_event("stt:final", self._on_stt_final)
            self._bound = False
            # cancel pending tasks
            for p in list(self.pending.values()):
                p.cancel()
            self.pending.clear()
            _log("stop: cleared pending and unbound events")

    # --- pending management ---
    def _new_pending(self, vad_id: str) -> PendingVad:
        p = PendingVad(vad_id)
        self.pending[vad_id] = p
        return p

    def _get_pending(self, vad_id: str) -> Optional[PendingVad]:
        return self.pending.get(vad_id)

    def _remove_pending(self, vad_id: str):
        if vad_id in self.pending:
            del self.pending[vad_id]

    # --- event handlers (sync callbacks that schedule async work) ---
    def _on_vad_start(self, meta: Optional[Dict[str, Any]] = None):
        try:
            vad_id = (meta or {}).get("vad_id") or f"vad-{int(time.time()*1000)}"
            agent_speaking = self.adapter.is_speaking()
            _log("vad:start", vad_id, "agent_speaking=", agent_speaking)
            p = self._new_pending(vad_id)
            # schedule debounce coroutine on event loop
            loop = None
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    p._task = loop.create_task(self._debounce_and_decide(p, agent_speaking))
                else:
                    # run in a new loop in background thread
                    def _bg():
                        asyncio.run(self._debounce_and_decide(p, agent_speaking))
                    threading.Thread(target=_bg, daemon=True).start()
            except RuntimeError:
                # no loop available — run in background thread
                def _bg():
                    asyncio.run(self._debounce_and_decide(p, agent_speaking))
                threading.Thread(target=_bg, daemon=True).start()
        except Exception:
            _log("error in _on_vad_start:", traceback.format_exc())

    def _on_vad_stop(self, meta: Optional[Dict[str, Any]] = None):
        try:
            vad_id = (meta or {}).get("vad_id")
            if not vad_id:
                return
            p = self._get_pending(vad_id)
            if p:
                p.cancel()
                _log("vad:stop cancelled", vad_id)
                self._remove_pending(vad_id)
        except Exception:
            _log("error in _on_vad_stop:", traceback.format_exc())

    def _on_stt_partial(self, meta: Optional[Dict[str, Any]] = None):
        try:
            vad_id = (meta or {}).get("vad_id")
            text = (meta or {}).get("text") or ""
            if vad_id:
                p = self._get_pending(vad_id)
                if p:
                    p.append(text)
            else:
                for p in list(self.pending.values()):
                    p.append(text)
            _log("stt.partial appended:", text)
        except Exception:
            _log("error in _on_stt_partial:", traceback.format_exc())

    def _on_stt_final(self, meta: Optional[Dict[str, Any]] = None):
        try:
            vad_id = (meta or {}).get("vad_id")
            text = (meta or {}).get("text") or ""
            if vad_id:
                p = self._get_pending(vad_id)
                if p:
                    p.append(text)
            else:
                for p in list(self.pending.values()):
                    p.append(text)
            _log("stt.final appended:", text)
        except Exception:
            _log("error in _on_stt_final:", traceback.format_exc())

    # --- core decision logic ---
    async def _debounce_and_decide(self, pending: PendingVad, agent_speaking: bool):
        try:
            fast_window_ms = int(os.getenv("STT_FAST_WINDOW_MS") or "150")
            confirm_required = int(os.getenv("STT_CONFIRM_PARTIALS") or "2")

            partial_count = 0
            last_len = 0
            start_ts = time.time()

            while True:
                if pending._done:
                    return

                txt = pending.combined()
                tokens = tokenize_transcript(txt)

                # 1) immediate explicit interrupt
                for tk in tokens:
                    if tk in INTERRUPT_WORDS:
                        _log("early explicit interrupt:", tk)
                        await self.adapter.stop_agent_audio()
                        if txt:
                            self.adapter.emit_user_input_event(txt)
                        pending._done = True
                        self._remove_pending(pending.vad_id)
                        return

                # update partial_count by checking transcript list length
                current_len = len(pending.transcripts)
                if current_len > last_len:
                    partial_count += (current_len - last_len)
                    last_len = current_len

                # 2) fast confirm when agent is speaking
                if agent_speaking:
                    non_ignore = [t for t in tokens if t and t not in IGNORE_WORDS]
                    if non_ignore and partial_count >= confirm_required:
                        _log("fast confirm interrupt (non-ignore tokens):", non_ignore)
                        await self.adapter.stop_agent_audio()
                        if txt:
                            self.adapter.emit_user_input_event(txt)
                        pending._done = True
                        self._remove_pending(pending.vad_id)
                        return

                # 3) max wait fallback
                elapsed_ms = (time.time() - start_ts) * 1000.0
                if elapsed_ms >= STT_MAX_WAIT_MS:
                    _log("max wait elapsed")
                    break

                # 4) debounce normal
                if elapsed_ms >= STT_DEBOUNCE_MS:
                    if not (agent_speaking and len(tokens) == 0):
                        _log("debounce elapsed -> evaluate")
                        break

                await asyncio.sleep(fast_window_ms / 1000.0)

            # final evaluate
            if pending._done:
                return
            final_txt = pending.combined()
            decision = self._evaluate(agent_speaking, final_txt)
            _log(f"vad decision id={pending.vad_id} interrupt={decision['interrupt']} reason={decision['reason']} text='{final_txt}'")
            if decision["interrupt"]:
                await self.adapter.stop_agent_audio()
                if final_txt:
                    self.adapter.emit_user_input_event(final_txt)
            else:
                self.adapter.continue_agent_audio()

        except asyncio.CancelledError:
            _log("debounce cancelled for", pending.vad_id)
        except Exception:
            _log("error in debounce_and_decide:\n", traceback.format_exc())
        finally:
            pending._done = True
            self._remove_pending(pending.vad_id)

    def _evaluate(self, agent_speaking: bool, transcript_text: str) -> Dict[str, Any]:
        txt = (transcript_text or "").strip().lower()
        if not txt:
            return {"interrupt": False, "reason": "no-transcript"}
        tokens = tokenize_transcript(txt)
        _log("tokens:", tokens)

        if agent_speaking and tokens:
            last_tok = tokens[-1]
            if last_tok in IGNORE_WORDS:
                if len(tokens) <= 3:
                    return {"interrupt": False, "reason": "trailing-filler-tolerance"}
                non_ignore_now = [t for t in tokens if t not in IGNORE_WORDS]
                if len(non_ignore_now) == 1 and len(tokens) <= 4:
                    return {"interrupt": False, "reason": "trailing-filler-single-content-tolerance"}

        for tk in tokens:
            if tk in INTERRUPT_WORDS:
                return {"interrupt": True, "reason": f"explicit-interrupt:{tk}"}

        if not agent_speaking:
            return {"interrupt": True, "reason": "agent-silent"}

        non_ignore = [t for t in tokens if t not in IGNORE_WORDS]
        if len(tokens) == 0 or len(non_ignore) == 0:
            return {"interrupt": False, "reason": "all-ignore-or-noise"}

        return {"interrupt": True, "reason": f"non-ignore-tokens:{','.join(non_ignore[:3])}"}
