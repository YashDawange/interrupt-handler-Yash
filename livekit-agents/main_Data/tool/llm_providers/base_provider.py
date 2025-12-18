#llm_providers/base_provider.py
from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    @abstractmethod
    def load_model(self):
        pass
    
    @abstractmethod
    def name(self) -> str:
        pass