import os
from dotenv import load_dotenv
load_dotenv()
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None # Handle missing deps gracefully
from .base_provider import BaseLLMProvider

class GPTProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name

    def load_model(self):
        if not ChatOpenAI: raise ImportError("pip install langchain-openai")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key: raise ValueError("OPENAI_API_KEY missing")
        return ChatOpenAI(model=self.model_name, api_key=api_key, temperature=0)

    def name(self) -> str: return "OpenAI GPT"