#engines/base_engine.py
import re
from .base_engine import BaseEngine

# --- NLTK Imports ---
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
# NOTE: You'll need to download these resources once:
# nltk.download('stopwords') 
# --------------------

class RulesEngine(BaseEngine):
    def __init__(self, ignore_words, interrupt_words):
        # Initialize NLTK components
        self.stop_words = set(stopwords.words('english'))
        self.stemmer = PorterStemmer()
        
        # Pre-process rule lists using the NLTK pipeline
        self.ignore = {self._norm_nltk(w) for w in ignore_words if w}
        self.interrupt = [self._norm_nltk(w) for w in interrupt_words if w]
        
        # Add common interjections/fillers to the ignore list, stemmed
        common_fillers = ["um", "uh", "like", "you know", "i mean", "right", "well"]
        self.ignore.update({self._norm_nltk(w) for w in common_fillers})

    # --- Enhanced Normalization with Stemming and Stop Word Removal ---
    def _norm(self, s: str) -> str:
        """A simple normalization for display/logging."""
        return re.sub(r"\s+", " ", s.lower().strip())
    
    def _norm_nltk(self, s: str) -> str:
        """Applies NLTK processing: lowercasing, tokenization, stemming, stop word removal."""
        s = self._norm(s) # Standardize whitespace and lower case
        
        # Tokenize
        tokens = re.split(r"\s+", s)
        
        # Stemming and Stop Word Removal
        processed_tokens = []
        for token in tokens:
            if token not in self.stop_words:
                processed_tokens.append(self.stemmer.stem(token))
                
        # Rejoin into a single string for comparison
        return " ".join(processed_tokens)

    async def classify(self, transcript: str, agent_is_speaking: bool, context: dict = None) -> dict:
        # Use the enhanced NLTK normalization for classification
        processed_text = self._norm_nltk(transcript or "")
        
        # 1. Check Hard Interrupts (Highest Priority)
        # Interrupts must be checked against the original processed text
        for cmd in self.interrupt:
            if cmd and (cmd in processed_text):
                # Reason updated to reflect better linguistic match
                return {"decision": "INTERRUPT", "score": 1.0, "reason": "linguistic_keyword_match"}

        # 2. Check Passive Ignore (Only if agent is speaking)
        if agent_is_speaking:
            # Tokenize the processed text
            tokens = [t for t in re.split(r"\s+", processed_text) if t]
            
            # Heuristic 1: Short content sentence (after stripping stop words)
            # A longer token list here means actual content was spoken.
            if len(tokens) <= 2: 
                # Heuristic 2: All remaining tokens are in the ignore list (now including stemmed fillers)
                if all(tok in self.ignore for tok in tokens):
                    return {"decision": "IGNORE", "score": 0.95, "reason": "passive_filler_nltk"}

        # 3. Default
        return {"decision": "NORMAL", "score": 0.0, "reason": "default"}