import os
import asyncio
import re
from typing import Iterable

# Config (can be overridden by env var or passed in)
DEFAULT_IGNORE_LIST = ['yeah', 'ok', 'hmm', 'right', 'uh-huh', 'okay', 'yep']
DEFAULT_HARD_LIST = ['wait', 'stop', 'no', 'pause', 'hold', 'sorry', 'listen']

# Simple normalization
def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s'-]", '', s)
    return s

class InterruptHandler:
    def __init__(self, agent, stt, *,
                 ignore_list: Iterable[str] = None,
                 hard_list: Iterable[str] = None,
                 partial_timeout: float = 0.28):
        """
        agent: object controlling agent playback and state (must implement is_speaking(), stop_and_listen(), handle_user_text())
        stt: object providing quick transcription (must implement quick_transcribe(audio_buffer, timeout))
        partial_timeout: how long to wait (seconds) for a quick transcript before deciding to ignore
        """
        self.agent = agent
        self.stt = stt
        self.ignore_list = set([x.lower() for x in (ignore_list or DEFAULT_IGNORE_LIST)])
        self.hard_list = set([x.lower() for x in (hard_list or DEFAULT_HARD_LIST)])
        self.partial_timeout = partial_timeout

        # Track pending tasks per user (to avoid double-work)
        self._pending = {}  # user_id -> asyncio.Task

        # Optionally expose config via environment
        env_ignore = os.getenv('SOFT_IGNORE_LIST')
        if env_ignore:
            self.ignore_list = set([t.strip().lower() for t in env_ignore.split(',') if t.strip()])

        env_hard = os.getenv('HARD_COMMAND_LIST')
        if env_hard:
            self.hard_list = set([t.strip().lower() for t in env_hard.split(',') if t.strip()])

    async def on_vad_start(self, user_id: str, audio_buffer):
        """
        Called by the VAD event handler when user audio starts / VAD flagged voice.
        audio_buffer: a reference or raw bytes chunk containing the recent user audio (last N ms).
        """
        # If agent silent -> accept immediately (normal conversational flow)
        if not self.agent.is_speaking():
            # Nothing to block: treat as normal user speech
            # Forward to normal handler immediately (agent should switch to listening)
            await self._handle_user_when_agent_silent(user_id, audio_buffer)
            return

        # Agent is speaking -> we must NOT stop immediately.
        # If we already have a pending evaluation, skip starting another.
        if user_id in self._pending:
            return

        # create a task to evaluate this transient VAD event
        task = asyncio.create_task(self._evaluate_while_speaking(user_id, audio_buffer))
        self._pending[user_id] = task

        def _cleanup(t):
            self._pending.pop(user_id, None)
        task.add_done_callback(_cleanup)

    async def _handle_user_when_agent_silent(self, user_id, audio_buffer):
        # Here the agent is silent; we should quickly transcribe and then pass to
        # the normal processing pipeline (no ignoring)
        try:
            transcript = await asyncio.wait_for(
                self.stt.quick_transcribe(audio_buffer),
                timeout=self.partial_timeout
            )
        except asyncio.TimeoutError:
            transcript = None

        # If no transcript available, let the agent still attempt to handle (some systems use direct wake)
        if transcript:
            transcript = normalize_text(transcript)
            # deliver to agent's normal flow
            await self.agent.handle_user_text(user_id, transcript)
        else:
            # fallback: tell agent to listen (no text)
            await self.agent.start_listening_for_user(user_id)

    async def _evaluate_while_speaking(self, user_id, audio_buffer):
        """
        While the agent is speaking, we wait a tiny amount of time for a quick STT.
        Decision rules:
          - If transcript contains any *hard* word -> interrupt immediately.
          - Else if transcript contains non-empty tokens not in ignore_list -> interrupt.
          - Else (empty or only soft tokens) -> ignore and do nothing.
        """
        try:
            # get quick transcript (STT should be tuned for low-latency partials)
            try:
                transcript = await asyncio.wait_for(self.stt.quick_transcribe(audio_buffer), timeout=self.partial_timeout)
            except asyncio.TimeoutError:
                transcript = None

            # If STT not available within timeout -> treat as soft / ignore
            if not transcript:
                # No reliable text -> continue speaking (do nothing)
                return

            text = normalize_text(transcript)
            if not text:
                return

            # Tokenize simply on whitespace
            tokens = [t for t in text.split() if t]

            # Check for any hard commands first (interrupt)
            for tok in tokens:
                if tok in self.hard_list:
                    # interrupt immediately
                    await self._do_interrupt(user_id, text)
                    return

            # If tokens contain anything that's not in ignore_list, treat as interruption.
            # This catches "yeah but wait" (but/wait not in ignore list -> interrupt).
            non_soft = [tok for tok in tokens if tok not in self.ignore_list]
            if non_soft:
                await self._do_interrupt(user_id, text)
                return

            # Otherwise: all tokens are soft -> ignore and do nothing (agent continues)
            return

        except Exception as e:
            # safe default: do not interrupt on handler failure
            # but log the error via agent logger if available
            try:
                self.agent.logger.exception("InterruptHandler error: %s", e)
            except Exception:
                pass
            return

    async def _do_interrupt(self, user_id, transcript_text):
        """
        Called when we decide to interrupt: stop agent speech and route transcript into normal processing.
        """
        # Immediately stop playback and hand off to listening/processing
        # IMPORTANT: stop_and_listen should be synchronous/fast, or at least not block for long.
        await self.agent.stop_and_listen(user_id)

        # If we have transcript text, feed it into agent's pipeline (optional)
        if transcript_text:
            await self.agent.handle_user_text(user_id, transcript_text)
