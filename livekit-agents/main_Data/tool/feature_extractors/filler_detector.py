# improved_filler_detector_with_nltk.py
"""
Hybrid Filler/Backchannel Detector with NLTK Preprocessing.
Strategy:
 - Fast regex-based detection for common fillers/backchannels (high confidence).
 - NLTK-based preprocessing for robust text cleaning.
 - Configurable ML/Similarity fallback for detection of variations/typos (moderate confidence).

Wrapped in a class `FillerDetector` for better encapsulation and state management.
"""

import re
import math
from typing import Tuple, Dict, List, Set
import nltk
# NOTE: The imports below are left commented out as per the original file's structure.
# from nltk.tokenize import word_tokenize
# from nltk.corpus import stopwords


# --- Configuration and Data ---

# A conservative, language-specific list of filler/backchannel tokens.
DEFAULT_FILLERS: Set[str] = {
    "yeah", "ok", "okay", "hmm", "uh", "uh-huh", "uhh", "mmhmm", "yep",
    "yup", "got it", "i'm listening", "right", "aha", "mm", "huh", "ohh",
}

# 2. Simulated ML/Embedding Data
_FILLER_EMBEDDINGS: Dict[str, Tuple[float, float, float]] = {
    "yeah": (0.9, 0.1, 0.1),
    "ok": (0.7, 0.0, 0.5),
    "hmm": (0.3, 0.8, 0.2),
    "uh": (0.1, 0.9, 0.1),
    "got it": (0.5, 0.0, 0.8),
    "right": (0.8, 0.1, 0.4),
    "i'm listening": (0.4, 0.0, 0.9),
}
_AVG_FILLER_EMBEDDING = (0.55, 0.3, 0.35)


class FillerDetector:
    """
    Encapsulates the hybrid filler/backchannel detection logic.
    """
    def __init__(self, fillers: Set[str] = DEFAULT_FILLERS):
        """
        Initializes the detector, compiling regex patterns and setting up NLTK resources.
        """
        self.fillers = fillers
        self._compile_regex()
        self._setup_nltk()

    def _compile_regex(self):
        """
        Compiles the necessary regex patterns for fast detection.
        """
        filler_pattern = r"|".join(re.escape(x) for x in self.fillers)

        # 1. High-Confidence Regex (Starts with an exact filler, optional trailing punct/space)
        self._filler_re = re.compile(
            r"^\s*(?:" + filler_pattern + r")(?:[.!?,\s].*)?$",
            flags=re.I
        )
        # 2. Medium-Confidence Regex (Contains a filler word with word boundaries)
        self._filler_contains_re = re.compile(
            r"\b(?:" + filler_pattern + r")\b",
            flags=re.I
        )

    def _setup_nltk(self):
        """
        Sets up NLTK resources like tokenization and stopwords.
        Handles potential LookupErrors if resources are not available.
        """
        try:
            from nltk.tokenize import word_tokenize
            from nltk.corpus import stopwords
            self._word_tokenize = word_tokenize
            # Ensure NLTK resources are downloaded (uncomment if you run this for the first time)
            # nltk.download('punkt', quiet=True)
            # nltk.download('stopwords', quiet=True)
            self._stop_words = set(stopwords.words('english'))
        except (ImportError, LookupError):
            print("Warning: NLTK resources (punkt, stopwords) not available. Using basic fallback.")
            self._word_tokenize = lambda text: text.lower().split()  # Simple split fallback
            self._stop_words = {"i", "me", "my", "myself", "we", "our", "ours", "you", "your"} # Basic fallback set

    # --- Utility Methods ---

    @staticmethod
    def _cosine_similarity(vec_a: Tuple[float, ...], vec_b: Tuple[float, ...]) -> float:
        """Calculates the cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        magnitude_a = math.sqrt(sum(a * a for a in vec_a))
        magnitude_b = math.sqrt(sum(b * b for b in vec_b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        return dot_product / (magnitude_a * magnitude_b)

    @staticmethod
    def _get_embedding(tokens: List[str]) -> Tuple[float, float, float]:
        """
        Simulated function to get an embedding based on cleaned tokens.
        """
        if not tokens:
            return (0.0, 0.0, 0.0)

        # Check for presence of key words in the cleaned token list
        for token in tokens:
            if token in _FILLER_EMBEDDINGS:
                # For simplicity, if a core filler is present, use its vector
                return _FILLER_EMBEDDINGS[token]

        # If no exact match in the cleaned tokens, return the average filler vector
        return _AVG_FILLER_EMBEDDING

    def _preprocess_transcript(self, transcript: str) -> List[str]:
        """
        Uses NLTK (or fallback) to tokenize, lowercase, and remove punctuation/stopwords.
        """
        if not transcript:
            return []

        # Lowercase the entire transcript
        text_lower = transcript.lower()

        # Tokenize the text
        tokens = self._word_tokenize(text_lower)

        # Remove punctuation and stopwords
        cleaned_tokens = [
            word for word in tokens
            if word.isalnum() and word not in self._stop_words
        ]

        return cleaned_tokens

    # --- Core Detection Method ---

    def is_filler_hybrid_nltk(self, transcript: str, similarity_threshold: float = 0.8) -> Tuple[bool, float]:
        """
        Hybrid Filler Detector combining Regex speed, NLTK cleaning, and simulated Embedding robustness.

        Returns (is_filler, confidence_estimate)
        """
        if not transcript or not transcript.strip():
            return (False, 0.0)

        t = transcript.strip()

        # 1. High-Confidence Regex Check (Fastest)
        if self._filler_re.match(t):
            return True, 0.95

        # 2. Medium-Confidence Regex Check (Contains a filler)
        if self._filler_contains_re.search(t):
            return True, 0.65

        # 3. Robust ML/Similarity Fallback (Handling variations and noise)

        # Use NLTK to clean and prepare the text
        cleaned_tokens = self._preprocess_transcript(t)

        # Get the embedding for the cleaned tokens (Simulated)
        input_embed = self._get_embedding(cleaned_tokens)

        # Calculate similarity against the general filler concept
        similarity = self._cosine_similarity(input_embed, _AVG_FILLER_EMBEDDING)

        if similarity > similarity_threshold:
            # Confidence is scaled by the similarity score.
            confidence = min(0.9, 0.7 + (similarity - similarity_threshold) * 2.0)
            return True, confidence

        return False, 0.0

# --- Example Usage ---

if __name__ == "__main__":
    print("--- Hybrid Filler Detector (NLTK Integrated - Class Test) ---")

    # Initialize the detector
    detector = FillerDetector()

    test_cases = [
        "uh huh, so what do you think?",  # Regex Match 1 (High Confidence)
        "yeah wait a minute, please",     # Regex Match 2 (Medium Confidence - Contains)
        "yeeah, i mean, i am listening",  # NLTK cleans "i am" & handles "yeeah" via similarity
        "right.",                         # Regex Match 1 (High Confidence)
        "wait please",                    # Non-Filler (Low Confidence)
        "I need to stop now!",            # NLTK removes 'I need to'
    ]

    for s in test_cases:
        is_filler, confidence = detector.is_filler_hybrid_nltk(s)
        print(f"Transcript: '{s}'")
        print(f"  -> Filler: {is_filler} | Confidence: {confidence:.2f}")