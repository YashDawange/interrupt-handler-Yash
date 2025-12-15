# agent/speech_manager.py
import asyncio
from typing import Callable, Optional

class SpeechManager:
    """
    Tracks whether the agent is currently speaking.
    Use start_speaking()/stop_speaking() around audio generation/playback.
    Provides a callback hook when speaking state changes.
    """

    def __init__(self):
        self._is_speaking = False
        self._lock = asyncio.Lock()
        self._on_state_change: Optional[Callable[[bool], None]] = None

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def set_state_change_callback(self, cb: Callable[[bool], None]):
        self._on_state_change = cb

    async def start_speaking(self):
        async with self._lock:
            self._is_speaking = True
            if self._on_state_change:
                try:
                    self._on_state_change(True)
                except Exception:
                    pass

    async def stop_speaking(self):
        async with self._lock:
            self._is_speaking = False
            if self._on_state_change:
                try:
                    self._on_state_change(False)
                except Exception:
                    pass

    # Convenience: wrap an async audio-play coroutine so state is set automatically.
    async def play_audio(self, audio_coro):
        await self.start_speaking()
        try:
            await audio_coro()
        finally:
            await self.stop_speaking()
