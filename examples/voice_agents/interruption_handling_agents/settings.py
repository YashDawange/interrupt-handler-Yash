from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class InterruptionSettings:
    """Configuration settings controlling interruption behavior."""
    cooldown_milliseconds: float = 300.0
    buffer_capacity: int = 20
    duplicate_window_seconds: float = 0.75
    interrupt_settle_delay_seconds: float = 0.25  # wait after interrupt before reply

    @classmethod
    def load_from_environment(cls) -> "InterruptionSettings":
        """Load interruption settings from environment variables."""
        return cls(
            cooldown_milliseconds=float(os.getenv("COOLDOWN_MS", "300")),
            buffer_capacity=int(os.getenv("BUFFER_CAP", "20")),
            duplicate_window_seconds=float(os.getenv("DUP_WINDOW_S", "0.75")),
            interrupt_settle_delay_seconds=float(os.getenv("INTERRUPT_SETTLE_S", "0.25")),
        )
