from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseEngine(ABC):
    """Strategy Interface for Interruption Logic."""
    
    @abstractmethod
    async def classify(self, transcript: str, agent_is_speaking: bool, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Returns:
            {
                "decision": "IGNORE" | "INTERRUPT" | "NORMAL",
                "score": float (0.0 - 1.0),
                "reason": str
            }
        """
        pass

    async def close(self):
        pass