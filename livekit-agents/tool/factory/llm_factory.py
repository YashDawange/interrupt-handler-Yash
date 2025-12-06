from ..llm_providers.gpt_provider import GPTProvider
from ..llm_providers.ollama_provider import OllamaProvider
# from ..llm_providers.gemini_provider import GeminiProvider

class LLMFactory:
    @staticmethod
    def create(provider: str, model_name: str):
        p = provider.lower()
        if p == "gpt": return GPTProvider(model_name).load_model()
        if p == "ollama": return OllamaProvider(model_name).load_model()
        # if p == "gemini": return GeminiProvider(model_name).load_model()
        raise ValueError(f"Unknown LLM provider: {provider}")