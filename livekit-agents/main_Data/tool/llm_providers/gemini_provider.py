#llm_providers/gemini_provider.py
import os
from dotenv import load_dotenv
load_dotenv()
# Attempt to import the necessary class, handling missing dependency gracefully
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # Handle missing deps gracefully

from .base_provider import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    """
    A provider class for loading and configuring Google's Gemini models
    using the LangChain integration.
    """
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """
        Initializes the GeminiProvider.

        Args:
            model_name (str): The specific Gemini model to use.
        """
        self.model_name = model_name

    def load_model(self):
        """
        Loads and returns the configured ChatGoogleGenerativeAI model instance.

        Raises:
            ImportError: If the 'langchain-google-genai' package is not installed.
            ValueError: If the 'GEMINI_API_KEY' environment variable is not set.

        Returns:
            ChatGoogleGenerativeAI: The initialized Gemini model.
        """
        if not ChatGoogleGenerativeAI:
            raise ImportError("Please install the necessary library: pip install langchain-google-genai")
        
        # Get the API key from environment variables
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing. Please set it in your .env file or system environment.")
        
        # Initialize the model with the specified model name, API key, and configuration
        return ChatGoogleGenerativeAI(
            model=self.model_name,
            api_key=api_key,
            temperature=0  # Setting a low temperature for deterministic/factual tasks
        )

    def name(self) -> str:
        """
        Returns the human-readable name of the provider.
        
        Returns:
            str: The provider name.
        """
        return "Google Gemini"