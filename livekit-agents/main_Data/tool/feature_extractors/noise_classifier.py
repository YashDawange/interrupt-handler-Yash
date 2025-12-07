# improved_noise_classifier_with_nltk.py
"""
Hybrid Noise Classifier using NLTK and Similarity, with a raw audio energy fallback.
Strategy:
 1. Raw energy check (highest confidence for silence/background).
 2. Fast heuristic/keyword checks (high confidence).
 3. NLTK-based preprocessing for robust cleaning.
 4. Simulated similarity fallback for generalized noise descriptions (moderate confidence).
"""

import re
import math
from typing import Tuple, List, Dict, Set
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string

# Ensure NLTK resources are downloaded (uncomment if needed)
try:
    # nltk.download('punkt', quiet=True)
    # nltk.download('stopwords', quiet=True)
    pass
except:
    pass

class NoiseClassifier:
    """
    A hybrid classifier for detecting noise-related transcripts and raw audio energy.
    """
    
    # --- Configuration and Data ---

    # Keywords for fast regex checking (Case-insensitive)
    _NOISE_KEYWORDS_RE = re.compile(r"\b(noise|traffic|breath|breathing|laughter|laugh|cough|background|static|click|hiss|wind|typing)\b", flags=re.I)

    # Token set for non-speech/short utterance check
    _NON_SPEECH_TOKENS = re.compile(r"^[hm]{1,4}|[ah]{1,4}$", flags=re.I)
    
    # Simulated ML/Embedding Data
    _NOISE_EMBEDDINGS: Dict[str, Tuple[float, float, float]] = {
        "traffic": (0.8, 0.1, 0.1),
        "cough": (0.2, 0.9, 0.1),
        "static": (0.1, 0.2, 0.8),
        "laughter": (0.6, 0.5, 0.1),
        "loud": (0.7, 0.4, 0.3),
        "sound": (0.5, 0.5, 0.5),
    }
    _AVG_NOISE_EMBEDDING = (0.5, 0.4, 0.4)
    
    def __init__(self):
        """Initializes the classifier and attempts to load NLTK stopwords."""
        self._STOP_WORDS: Set[str] = set()
        try:
            self._STOP_WORDS = set(stopwords.words('english'))
        except LookupError:
            self._STOP_WORDS = {"i", "me", "my", "myself", "we", "our", "is", "a", "the", "it"}
            print("Warning: NLTK stopwords not found. Using simple fallback list.")


    # --- Raw Audio Processing (Static Method) ---
    
    @staticmethod
    def is_noise_by_energy(rms: float, energy_threshold: float = 1e-4) -> Tuple[bool, float]:
        """
        Simple RMS energy threshold detector.
        
        This is typically used for **silence** detection, where low energy 
        implies the recorded segment is background noise/silence rather than speech.
        
        Returns (is_noise/silence, confidence_estimate)
        """
        is_silence = rms < energy_threshold
        # If it's silence (low RMS), confidence is high that it's just background/noise.
        return (is_silence, 0.85 if is_silence else 0.0)

    # --- Utility Methods ---

    def _cosine_similarity(self, vec_a: Tuple[float, ...], vec_b: Tuple[float, ...]) -> float:
        """Calculates the cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        magnitude_a = math.sqrt(sum(a * a for a in vec_a))
        magnitude_b = math.sqrt(sum(b * b for b in vec_b))
        
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        return dot_product / (magnitude_a * magnitude_b)

    def _get_embedding(self, tokens: List[str]) -> Tuple[float, float, float]:
        """
        Simulated function to get an embedding based on cleaned tokens.
        Averages the vectors of known noise-descriptor words.
        """
        
        if not tokens:
            return (0.0, 0.0, 0.0)
        
        relevant_embeds = [
            self._NOISE_EMBEDDINGS[token] 
            for token in tokens 
            if token in self._NOISE_EMBEDDINGS
        ]
        
        if not relevant_embeds:
            return (0.0, 0.0, 0.0) 

        sum_embed = [sum(dim) for dim in zip(*relevant_embeds)]
        num_embeds = len(relevant_embeds)
        avg_embed = tuple(s / num_embeds for s in sum_embed)

        return avg_embed

    # --- NLTK Preprocessing Function ---

    def _preprocess_transcript(self, transcript: str) -> List[str]:
        """
        Uses NLTK to tokenize, lowercase, remove punctuation, and stopwords.
        """
        if not transcript:
            return []
        
        text_lower = transcript.lower()
        tokens = word_tokenize(text_lower)
        
        cleaned_tokens = [
            word for word in tokens
            if word not in self._STOP_WORDS and word not in string.punctuation and len(word) > 1
        ]
        
        return cleaned_tokens

    # --- Core Transcript Detection Function ---

    def is_noise_hybrid_nltk(self, transcript: str, similarity_threshold: float = 0.8) -> Tuple[bool, float]:
        """
        Hybrid Noise Classifier combining heuristics, NLTK cleaning, and simulated Embedding robustness 
        based on the transcript content.
        
        Returns (is_noise, confidence_estimate)
        """
        if transcript is None:
            return True, 0.6 

        t = transcript.strip()
        
        # 1. High-Confidence Heuristic Checks (Fastest)
        if t == "":
            # Empty transcript (but VAD fired)
            return True, 0.9
        
        # Short non-speech/non-alphanumeric tokens (e.g., 'mmm', 'huh')
        if re.fullmatch(self._NON_SPEECH_TOKENS, t.lower()) or re.fullmatch(r"[^\w\s]{0,2}", t):
            return True, 0.85

        # 2. Keyword Check (Moderate Confidence)
        if self._NOISE_KEYWORDS_RE.search(t):
            return True, 0.75
        
        # 3. Robust ML/Similarity Fallback
        
        cleaned_tokens = self._preprocess_transcript(t)
        input_embed = self._get_embedding(cleaned_tokens)
        similarity = self._cosine_similarity(input_embed, self._AVG_NOISE_EMBEDDING)
        
        if similarity > similarity_threshold:
            confidence = min(0.9, 0.7 + (similarity - similarity_threshold) * 2.0)
            return True, confidence
            
        return False, 0.0

# --- Example Usage ---

if __name__ == "__main__":
    print("--- Hybrid Noise Classifier (Integrated Test) ---")
    
    classifier = NoiseClassifier()

    print("\n## A. Transcript-Based Tests")
    print("--------------------------------")
    transcript_test_cases = [
        "",                             
        "traffic noise is quite loud",  
        "mmm",                          
        "it was a loud static sound",   
        "I heard breathing sounds",      
        "I'm talking now",              
    ]

    for s in transcript_test_cases:
        is_noise, confidence = classifier.is_noise_hybrid_nltk(s)
        print(f"Transcript: '{s}'")
        print(f"  -> Noise: {is_noise} | Confidence: {confidence:.2f}")

    print("\n## B. Raw Audio (RMS Energy) Tests")
    print("-----------------------------------")
    # RMS values are typically very small for normalized audio silence
    rms_test_cases = [
        (1e-5, "Low RMS (Silence/Background)"),
        (0.1, "High RMS (Loud Speech/Signal)"),
        (1e-4, "Boundary RMS"),
    ]
    energy_threshold = 1e-4

    for rms, description in rms_test_cases:
        is_noise, confidence = NoiseClassifier.is_noise_by_energy(rms, energy_threshold=energy_threshold)
        print(f"RMS: {rms:.1e} (Threshold: {energy_threshold:.1e})")
        print(f"  -> Noise: {is_noise} | Confidence: {confidence:.2f} | ({description})")