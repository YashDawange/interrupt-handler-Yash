import os
from dotenv import load_dotenv

# Load environment variables (API keys) from .env file
load_dotenv()

# --- Configuration ---
# Set a simple prompt for the models to answer
SIMPLE_PROMPT = "Explain the difference between a list and a tuple in Python in one sentence."

# --- Import Providers ---
# Assuming 'llm_providers' is in the same directory or on the Python path
try:
    from ..gpt_provider import GPTProvider
    from ..gemini_provider import GeminiProvider
    from ..ollama_provider import OllamaProvider
except ImportError as e:
    print(f"Error importing providers: {e}")
    print("Ensure your project structure is correct and the files are in 'llm_providers/'")
    exit(1)


def run_test(provider):
    """
    Instantiates the model and calls the API with a simple prompt.
    """
    provider_name = provider.name()
    print(f"\n--- Running Test for {provider_name} ---")

    try:
        # 1. Load the model
        model = provider.load_model()
        print(f"✅ Model loaded successfully: {model.model_name}")

        # 2. Invoke the model
        print(f"❓ Prompt: {SIMPLE_PROMPT}")
        response = model.invoke(SIMPLE_PROMPT)

        # 3. Print the response
        print(f"🤖 Response:")
        # The .content attribute holds the string response from the model
        print(response.content)
        
    except ValueError as e:
        # Catches missing API Key error
        print(f"❌ Failed to run {provider_name}. API Key Error: {e}")
        print(f"   Please ensure the required API key ({provider_name.split()[1]}_API_KEY) is set.")
    except ImportError as e:
        # Catches missing dependency error
        print(f"❌ Failed to run {provider_name}. Dependency Error: {e}")
        print("   Run 'pip install langchain-openai langchain-google-genai'.")
    except Exception as e:
        # Catches other potential API or connection errors
        print(f"❌ An unexpected error occurred with {provider_name}: {e}")

if __name__ == "__main__":
    
    # -----------------------------------
    # Test OpenAI GPT
    # Requires: OPENAI_API_KEY
    # -----------------------------------
    gpt_provider = GPTProvider()
    run_test(gpt_provider)

    # -----------------------------------
    # Test Google Gemini
    # Requires: GEMINI_API_KEY
    # -----------------------------------
    gemini_provider = GeminiProvider()
    run_test(gemini_provider)
        
    # -----------------------------------
    # Test Ollama 
    # -----------------------------------
    ollama_provider = OllamaProvider()
    run_test(ollama_provider)