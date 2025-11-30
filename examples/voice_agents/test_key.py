import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key)

print("🔍 Checking models (New SDK)...")
try:
    # 1. Get the list of models
    # The new SDK returns an iterable, not a list
    for model in client.models.list():
        
        # 2. Check capabilities using the NEW attribute name: 'supported_actions'
        # We look for 'generateContent' which means it can chat
        if hasattr(model, "supported_actions") and "generateContent" in model.supported_actions:
            print(f"✅ Available: {model.name}")
            
except Exception as e:
    print(f"❌ Error: {e}")