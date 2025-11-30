import time
from typing import Optional, Dict

class Logger:
    """Structured logger for agent events."""
    
    def __init__(self, name: str = "smart-agent"):
        self.name = name

    def log_input(self, text: str, is_final: bool, agent_state: str):
        status = "final" if is_final else "interim"
        print(f"[{self.name}] [INPUT] text='{text}' status={status} agent_state={agent_state}")

    def log_classification(self, text: str, intent: str):
        print(f"[{self.name}] [CLASSIFY] text='{text}' -> {intent}")

    def log_decision(self, decision: str, reason: str):
        print(f"[{self.name}] [DECIDE] {decision}: {reason}")

    def log_action(self, action: str, details: str = ""):
        msg = f"[{self.name}] [EXECUTE] {action}"
        if details:
            msg += f" ({details})"
        print(msg)

    def log_error(self, msg: str, exc: Optional[Exception] = None):
        print(f"[{self.name}] [ERROR] {msg} {exc if exc else ''}")


class UtteranceTracker:
    """Tracks recent utterances to prevent duplicate processing."""
    
    def __init__(self, max_size: int, window_seconds: float):
        self._buffer: Dict[str, float] = {}
        self._max_size = max_size
        self._window = window_seconds

    def is_duplicate(self, text: str) -> bool:
        """Check if text was seen recently."""
        now = time.time()
        last_seen = self._buffer.get(text)
        if last_seen and (now - last_seen) < self._window:
            return True
        return False

    def add(self, text: str):
        """Add text to buffer, evicting old entries if needed."""
        now = time.time()
        self._buffer[text] = now
        
        # Simple eviction if over capacity
        if len(self._buffer) > self._max_size:
            # Remove oldest
            oldest = min(self._buffer.items(), key=lambda x: x[1])[0]
            del self._buffer[oldest]
