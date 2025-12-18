# state_observer.py
import asyncio
from typing import Callable

class AgentStateObserver:
    def __init__(self):
        self._speaking = False
        self._callbacks = []

    def is_speaking(self) -> bool:
        return self._speaking

    def on_speaking_start(self):
        self._speaking = True
        for cb in self._callbacks:
            cb(self._speaking)

    def on_speaking_end(self):
        self._speaking = False
        for cb in self._callbacks:
            cb(self._speaking)

    def register_callback(self, cb: Callable[[bool], None]):
        self._callbacks.append(cb)