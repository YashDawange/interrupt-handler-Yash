# low_latency_semantic_intent_classifier.py
"""
Low-Latency Semantic Intent Classifier (INTERRUPT / IGNORE / NORMAL).
- Purely heuristic and NLTK-based for high speed and low latency.
- LLM fallback has been removed entirely.
- Uses hybrid filler and noise checks.
"""

from typing import Dict, Tuple, List
import re
import math
import nltk
from nltk.tokenize import word_tokenize
# Assuming filler_detector and noise_classifier are updated and available
# NOTE: Ensure you use the NLTK-integrated versions of the helpers:
# from .filler_detector_with_nltk import is_filler_hybrid_nltk
# from .noise_classifier_with_nltk import is_noise_hybrid_nltk

# --- Placeholder Imports for Demonstration ---
# In a real environment, these would be your actual imported modules
def is_filler_hybrid_nltk(transcript: str) -> Tuple[bool, float]:
    """Mock filler check"""
    return "yeah" in transcript.lower(), 0.7 if "yeah" in transcript.lower() else 0.0
def is_noise_hybrid_nltk(transcript: str) -> Tuple[bool, float]:
    """Mock noise check"""
    return "noise" in transcript.lower(), 0.8 if "noise" in transcript.lower() else 0.0

# --- Robust Interrupt Keyword Detection (NLTK + Similarity) ---

INTERRUPT_KEYWORDS = ["stop", "wait", "pause", "hold on", "no", "don't", "hang on", "hold up", "interrupt", "cease"]

# 1. High Priority Regex (Kept for speed on exact matches)
HIGH_PRIORITY_RE = re.compile(r"\b(?:" + r"|".join(re.escape(x) for x in INTERRUPT_KEYWORDS) + r")\b", flags=re.I)

# 2. Simulated Embedding Data for Interrupt Functionality
# D1: Command/Imperative, D2: Time/Delay, D3: Negation/Rejection
_INTERRUPT_EMBEDDINGS: Dict[str, Tuple[float, float, float]] = {
    "stop": (0.9, 0.1, 0.1), "wait": (0.5, 0.8, 0.1), "no": (0.1, 0.1, 0.9),
    "hold on": (0.6, 0.7, 0.1), "cease": (0.8, 0.2, 0.1)
}
_AVG_INTERRUPT_EMBEDDING = (0.5, 0.5, 0.4)
_INTERRUPT_SIM_THRESHOLD = 0.85 # High threshold for classification

# --- Utility Functions ---

def _cosine_similarity(vec_a: Tuple[float, ...], vec_b: Tuple[float, ...]) -> float:
    """Calculates the cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)

def _get_interrupt_embedding(tokens: List[str]) -> Tuple[float, float, float]:
    """
    Simulated function to get an embedding based on cleaned tokens.
    """
    if not tokens:
        return (0.0, 0.0, 0.0)
    for token in tokens:
        if token in _INTERRUPT_EMBEDDINGS:
            return _INTERRUPT_EMBEDDINGS[token]
    return _AVG_INTERRUPT_EMBEDDING

def _preprocess_transcript(transcript: str) -> List[str]:
    """Uses NLTK to tokenize and lowercase the transcript."""
    if not transcript:
        return []
    
    text_lower = transcript.lower()
    # Using a try/except block for NLTK usage safety in different environments
    try:
        tokens = word_tokenize(text_lower)
    except LookupError:
        # Fallback if NLTK punkt is not downloaded
        tokens = text_lower.split() 
        
    # Filter out punctuation
    tokens = [t for t in tokens if t.isalnum()]
    
    return tokens

# --- Core Classifier Class ---

class SemanticIntentClassifier:
    """
    Classifies intent (INTERRUPT / IGNORE / NORMAL) using low-latency, 
    non-LLM techniques (Regex, Heuristics, NLTK Similarity).
    """
    def __init__(self):
        # LLM initialization removed entirely
        pass 

    async def classify(self, transcript: str, agent_is_speaking: bool, features: Dict = None) -> Dict:
        """
        Returns dict: {"decision": "INTERRUPT"/"IGNORE"/"NORMAL", "score": float, "meta": {...}}
        """
        
        # 0. NLTK Preprocessing
        tokens = _preprocess_transcript(transcript)
        
        # 1) IGNORE: Noise check (using the hybrid classifier)
        is_noise, noise_conf = is_noise_hybrid_nltk(transcript)
        if is_noise and noise_conf > 0.6:
            return {"decision": "IGNORE", "score": noise_conf, "meta": {"reason": "noise_hybrid"}}

        # 2) IGNORE: Filler/Backchannel check (using the hybrid classifier)
        is_filler, filler_conf = is_filler_hybrid_nltk(transcript)
        if agent_is_speaking and is_filler and filler_conf > 0.7:
            # Agent is speaking, user filler is usually a backchannel -> IGNORE
            return {"decision": "IGNORE", "score": filler_conf, "meta": {"reason": "filler_hybrid_backchannel"}}

        # 3) INTERRUPT: high priority checks (Hybrid - Keyword/Similarity)

        # a) Exact/Keyword Match (Fastest)
        if HIGH_PRIORITY_RE.search(transcript or ""):
            return {"decision": "INTERRUPT", "score": 0.95, "meta": {"reason": "explicit_keyword"}}
            
        # b) Similarity Match (Robustness against variations/typos)
        input_embed = _get_interrupt_embedding(tokens)
        similarity = _cosine_similarity(input_embed, _AVG_INTERRUPT_EMBEDDING)
        
        if similarity > _INTERRUPT_SIM_THRESHOLD:
            # Detected based on functional similarity (e.g., "stop it", "halt")
            sim_conf = min(0.9, 0.75 + (similarity - _INTERRUPT_SIM_THRESHOLD) * 2.0)
            return {"decision": "INTERRUPT", "score": sim_conf, "meta": {"reason": "interrupt_similarity"}}

        # 4) NORMAL: Filler while silent -> PASSIVE reply
        if not agent_is_speaking and is_filler:
            # Agent is silent, user filler is a passive reply/affirmation -> NORMAL
            return {"decision": "NORMAL", "score": filler_conf, "meta": {"reason": "filler_while_silent"}}

        # 5) Final Fallback Default (Handles all remaining long/unambiguous utterances)
        # Since we removed the LLM, this is the definitive result for all non-interrupt/non-ignore text.
        return {"decision": "NORMAL", "score": 0.6, "meta": {"reason": "final_fallback_to_normal"}}

# Example usage (mocked sync run):
if __name__ == "__main__":
    import asyncio
    
    # Initialize without LLM
    cls = SemanticIntentClassifier()
    
    print("--- Low-Latency Semantic Intent Classifier Test (LLM-Free) ---")
    
    test_cases = [
        ("stop the music now!", True, "High Confidence Interrupt (Keyword)"),
        ("hold up for a sec", True, "Robust Interrupt (Similarity)"),
        ("yeah ok", True, "Ignore (Filler/Backchannel)"),
        ("yeah ok", False, "Normal (Filler while silent)"),
        ("I hear some wind noise", True, "Ignore (Noise)"),
        ("I'm asking about the price", True, "Normal (Long text, Fallback)"),
        ("no no no", True, "Interrupt (Keyword repetition)"),
        ("can you tell me about the weather", True, "Normal (General Query)"),
    ]

    # Mock the async call with a synchronous wrapper for testing printout
    def sync_classify(transcript, agent_is_speaking):
        # We don't actually need asyncio here since there's no awaitable call (LLM removed)
        return cls.classify(transcript, agent_is_speaking) 

    for transcript, agent_speaking, description in test_cases:
        result = sync_classify(transcript, agent_speaking)
        print(f"[{description}] | Transcript: '{transcript}' (Agent Speaking: {agent_speaking})")
        print(f"  -> Decision: **{result['decision']}** | Score: {result['score']:.2f} | Reason: {result['meta']['reason']}")