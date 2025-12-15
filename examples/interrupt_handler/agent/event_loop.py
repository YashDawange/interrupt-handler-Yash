# agent/event_loop.py
import asyncio
import logging
from typing import Optional

from .speech_manager import SpeechManager
from .interrupt_filter import (
    contains_ignore_word,
    contains_interrupt_word,
    is_mixed_input,
    normalize_text,
)

LOG = logging.getLogger("interrupt_handler")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    LOG.addHandler(ch)

class InterruptHandler:
    """
    InterruptHandler mediates VAD triggers and STT transcripts against the agent's
    speaking state (via SpeechManager). Integrate on_vad_triggered() with the VAD
    event and on_transcription() with the STT/ASR result callback.

    Use:
      handler = InterruptHandler(speech_manager, on_interrupt_cb, on_input_cb)
    """

    def __init__(self, speech_manager: SpeechManager, on_interrupt_callback, on_user_input_callback):
        """
        on_interrupt_callback(text) -> called when we decide to interrupt the agent (stop speaking)
        on_user_input_callback(text) -> called when user input should be handled (agent silent case)
        """
        self.speech_manager = speech_manager
        self.on_interrupt = on_interrupt_callback
        self.on_user_input = on_user_input_callback

        # Flag set when VAD reports activity while we are speaking
        self._pending_vad = False
        # Protect internal state
        self._lock = asyncio.Lock()

        # Optional: timeout to clear pending flag if no STT arrives.
        self._pending_timeout_seconds = 0.6  # must be imperceptible; adjust as needed

    async def on_vad_triggered(self):
        """
        Called immediately when VAD detects voice activity.
        Must be non-blocking and fast.
        """
        async with self._lock:
            if self.speech_manager.is_speaking:
                # We do NOT stop the audio immediately.
                # We mark pending and wait for STT to confirm semantics.
                self._pending_vad = True
                LOG.debug("VAD while speaking -> pending_vad set True")
                # start a timer to clear pending_vad if no STT comes in short time
                asyncio.create_task(self._clear_pending_after_timeout())
            else:
                # Agent is silent: treat this as user input ready to be processed.
                LOG.debug("VAD while silent -> treating as immediate input (request STT)")
                # In real integration: you'd trigger transcription pipeline and call on_transcription when ready
                # Here we do NOT call on_user_input since transcription hasn't arrived yet.

    async def _clear_pending_after_timeout(self):
        await asyncio.sleep(self._pending_timeout_seconds)
        async with self._lock:
            if self._pending_vad:
                LOG.debug("pending_vad timeout elapsed; clearing pending_vad")
                self._pending_vad = False

    async def on_transcription(self, text: str):
        """
        Called when STT returns a transcription chunk. Must be awaited.
        """
        text_norm = normalize_text(text)
        LOG.info(f"STT -> '{text_norm}'")

        async with self._lock:
            if self.speech_manager.is_speaking and self._pending_vad:
                # Decide semantically
                if contains_interrupt_word(text_norm):
                    LOG.info("Decision: INTERRUPT (contains interrupt word). Stopping agent.")
                    self._pending_vad = False
                    await self._do_interrupt(text_norm)
                    return

                if contains_ignore_word(text_norm) and not contains_interrupt_word(text_norm):
                    LOG.info("Decision: IGNORE (only ignore words). Continue speaking.")
                    self._pending_vad = False
                    return

                # Mixed inputs or none matched -> if contains interrupt word anywhere, interrupt
                if is_mixed_input(text_norm) or contains_interrupt_word(text_norm):
                    LOG.info("Decision: MIXED/INTERRUPT. Stopping agent.")
                    self._pending_vad = False
                    await self._do_interrupt(text_norm)
                    return

                # default: ignore
                LOG.info("Decision: default IGNORE while speaking.")
                self._pending_vad = False
                return
            else:
                # Agent silent or no pending VAD: treat as normal user input
                LOG.info("Agent silent or no pending VAD -> handle as user input.")
                await self._handle_user_input(text_norm)

    async def _do_interrupt(self, text):
        # Stop speaking immediately (user asked to interrupt)
        # The actual stop should cancel audio playback / TTS streaming.
        try:
            await self.speech_manager.stop_speaking()
        except Exception:
            LOG.exception("Exception while stopping speaking")
        # Forward the interrupt text to the agent to handle the command
        await self.on_interrupt(text)

    async def _handle_user_input(self, text):
        # When agent is silent, treat the text as user input normally
        await self.on_user_input(text)
