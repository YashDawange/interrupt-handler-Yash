import os
from dataclasses import dataclass

@dataclass
class AgentConfig:
    """Configuration settings for the Smart Interruption Agent."""
    
    # Timing parameters
    cooldown_ms: float = 300.0
    duplicate_window_seconds: float = 0.75
    interrupt_settle_delay_seconds: float = 0.25
    
    # Buffer size
    transcript_buffer_size: int = 20
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            cooldown_ms=float(os.getenv("COOLDOWN_MS", "300")),
            duplicate_window_seconds=float(os.getenv("DUP_WINDOW_S", "0.75")),
            interrupt_settle_delay_seconds=float(os.getenv("INTERRUPT_SETTLE_S", "0.25")),
            transcript_buffer_size=int(os.getenv("BUFFER_CAP", "20")),
        )
