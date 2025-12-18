# engines/ML_engine.py
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from .base_engine import BaseEngine # Assuming this is in the same package structure

# --- Configuration from run_model.py ---
# Ensure this directory exists and contains your model files (config.json, pytorch_model.bin, tokenizer files)
MODEL_DIR = "interruption_model" 
MAX_LENGTH = 64 # Max length used during training/evaluation

# Label mapping must match the one used during training/evaluation
LABEL2ID = {"ignore": 0, "interrupt": 1, "response": 2}
ID2LABEL = {v: k for k, v in LABEL2ID.items()}
# ----------------------------------------


class MLEngine(BaseEngine):
    """
    Implements inference for the sequence classification model (e.g., interruption prediction)
    using a Hugging Face Transformers model loaded via PyTorch.
    """
    def __init__(self, model_path: str = MODEL_DIR):
        """
        Loads the tokenizer and the model from the specified path during initialization.
        """
        self.model_path = model_path
        self.tokenizer = None
        self.model = None
        self._load_model()
        
    def _load_model(self):
        """Helper to load the model and tokenizer."""
        try:
            print(f"Loading ML model and tokenizer from '{self.model_path}'...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
            self.model.eval() # Set model to evaluation mode
            print("ML Model loaded successfully.")
        except Exception as e:
            print(f"Error loading ML model: {e}")
            print(f"Please ensure the directory '{self.model_path}' exists and contains all necessary files (config.json, pytorch_model.bin, and tokenizer files).")
            # In a real application, you might raise an exception or set a flag to disable the engine.
            # For this example, we'll let it try to continue, but inference will fail without the model.
            self.model = None

    async def classify(self, transcript: str, agent_is_speaking: bool, context: dict = None) -> dict:
        """
        Runs inference on the provided transcript using the loaded model.

        Args:
            transcript (str): The text message from the user.
            agent_is_speaking (bool): Whether the agent is currently speaking (unused in this text-only model, but kept for signature).
            context (dict): Additional context like audio features (unused in this text-only model).

        Returns:
            dict: The decision, prediction score, and reason.
        """
        # Check if the model was loaded successfully
        if self.model is None or self.tokenizer is None:
            return {"decision": "ERROR", "score": 0.0, "reason": "Model not loaded"}
            
        if not isinstance(transcript, str) or not transcript.strip():
            # Match run_model.py's empty input handling but return the required dict structure
            return {"decision": "IGNORE", "score": 0.0, "reason": "Empty input"}

        # 1. Tokenize the input (using logic from run_model.py)
        enc = self.tokenizer(
            transcript,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH
        )

        # 2. Perform Inference
        with torch.no_grad():
            # The model returns a tuple where the first element is the logits tensor
            logits = self.model(**enc).logits 
            
            # Calculate probabilities (optional, but gives a score)
            probabilities = torch.softmax(logits, dim=-1)
            
            # Get the predicted class ID
            pred_id = torch.argmax(logits, dim=-1).item()
            
            # Get the confidence score for the predicted class
            pred_score = probabilities[0, pred_id].item()

        # 3. Convert prediction ID to human-readable label
        decision_raw = ID2LABEL.get(pred_id, "UNKNOWN")
        decision = decision_raw.upper()

        # 4. Return the result in the required format
        return {
            "decision": decision, 
            "score": round(pred_score, 4), # Round score for cleaner output
            "reason": f"ml_model_prediction_{decision_raw}"
        }

# Example of how you would integrate this into your main system:
# from engines.ML_engine import MLEngine
# ml_engine = MLEngine()
# result = await ml_engine.classify(transcript="Hey, wait a minute!", agent_is_speaking=True)
# print(result)