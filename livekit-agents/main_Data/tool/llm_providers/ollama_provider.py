#llm_providers/ollama_provider.py
try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None
from .base_provider import BaseLLMProvider

class OllamaProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def load_model(self):
        if not ChatOllama: raise ImportError("pip install langchain-ollama")
        return ChatOllama(model=self.model_name, temperature=0)

    def name(self) -> str: return "Ollama"