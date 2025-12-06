import threading

class AgentState:
    def __init__(self):
        self._lock = threading.Lock()
        self._is_speaking = False
        self._pending_vad = False

    def set_speaking(self, value: bool):
        with self._lock:
            self._is_speaking = bool(value)

    def is_speaking(self) -> bool:
        with self._lock:
            return self._is_speaking

    def set_pending_vad(self, value: bool):
        with self._lock:
            self._pending_vad = bool(value)

    def get_pending_vad(self) -> bool:
        with self._lock:
            return self._pending_vad

# singleton
GLOBAL_STATE = AgentState()
