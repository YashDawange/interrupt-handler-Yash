"""
ML-Based Backchannel Intent Classifier

Uses lightweight sentence embeddings to classify user utterances as:
- Backchannel (acknowledgment, listening feedback)
- Command (interruption, question, instruction)

Benefits over word matching:
- Language-agnostic
- Handles variations and context
- Learns from data
- Provides confidence scores

Uses sentence-transformers for embeddings (optional dependency).
Falls back to rule-based if not available.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

logger = logging.getLogger(__name__)

# Try to import sentence-transformers (optional)
try:
    from sentence_transformers import SentenceTransformer
    
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.info(
        "sentence-transformers not available. "
        "Install with: pip install sentence-transformers"
    )


@dataclass
class ClassificationResult:
    """Result of intent classification."""
    
    is_backchannel: bool
    confidence: float  # 0-1
    embedding: np.ndarray | None
    processing_time_ms: float
    method: str  # "ml" or "fallback"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "is_backchannel": self.is_backchannel,
            "confidence": round(self.confidence, 3),
            "processing_time_ms": round(self.processing_time_ms, 2),
            "method": self.method,
        }


class BackchannelClassifier:
    """
    ML-based classifier for backchannel detection.
    
    Uses sentence embeddings + cosine similarity to known patterns.
    Lightweight and fast (<10ms per classification).
    """
    
    # Example backchannel patterns (multilingual)
    BACKCHANNEL_PATTERNS = [
        # English
        "yeah", "ok", "okay", "uh-huh", "mm-hmm", "right", "sure",
        "got it", "I see", "alright", "yep", "yup", "mhm", "aha",
        # Spanish
        "sí", "vale", "claro", "ajá", "entiendo",
        # French
        "oui", "d'accord", "mmh", "je vois",
        # German
        "ja", "okay", "verstehe", "genau",
        # Mandarin (pinyin)
        "hao", "dui", "mingbai",
        # Japanese (romaji)
        "hai", "un", "ee", "naruhodo",
        # Korean (romanized)
        "ne", "eung", "araso",
        # Hindi (romanized)
        "haan", "theek", "acha",
        # Arabic (romanized)
        "na'am", "aywa", "tayyib",
    ]
    
    # Example command patterns
    COMMAND_PATTERNS = [
        # English
        "wait", "stop", "hold on", "listen", "no", "repeat",
        "what", "why", "how", "tell me", "explain", "show me",
        # Spanish
        "espera", "para", "no", "qué", "cómo",
        # French
        "attends", "arrête", "non", "quoi", "comment",
        # German
        "warte", "halt", "nein", "was", "wie",
        # Mandarin
        "deng", "ting", "bu", "shenme",
        # Japanese
        "matte", "yamete", "iie", "nani",
        # Korean
        "jamkkanman", "meomchwo", "ani", "mwo",
        # Hindi
        "ruko", "mat karo", "nahin", "kya",
        # Arabic
        "intazir", "qif", "la", "matha",
    ]
    
    def __init__(
        self,
        *,
        model_name: str = "all-MiniLM-L6-v2",
        confidence_threshold: float = 0.6,
        enable_cache: bool = True,
    ):
        """
        Initialize classifier.
        
        Args:
            model_name: Sentence transformer model name
            confidence_threshold: Minimum confidence for classification
            enable_cache: Whether to cache embeddings
        """
        self._model_name = model_name
        self._confidence_threshold = confidence_threshold
        self._enable_cache = enable_cache
        
        # Try to load model
        self._model = None
        self._backchannel_embeddings = None
        self._command_embeddings = None
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self._load_model()
            except Exception as e:
                logger.warning(f"Failed to load sentence transformer: {e}")
        
        # Embedding cache
        self._embedding_cache: dict[str, np.ndarray] = {}
        
        # Statistics
        self._stats = {
            "total_classifications": 0,
            "ml_classifications": 0,
            "fallback_classifications": 0,
            "avg_processing_time_ms": 0.0,
        }
    
    def _load_model(self) -> None:
        """Load sentence transformer model and precompute pattern embeddings."""
        logger.info(f"Loading sentence transformer model: {self._model_name}")
        start = time.time()
        
        # Load model
        self._model = SentenceTransformer(self._model_name)
        
        # Precompute pattern embeddings
        self._backchannel_embeddings = self._model.encode(
            self.BACKCHANNEL_PATTERNS,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        
        self._command_embeddings = self._model.encode(
            self.COMMAND_PATTERNS,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        
        elapsed = time.time() - start
        logger.info(f"Model loaded in {elapsed:.2f}s")
    
    def classify(self, text: str) -> ClassificationResult:
        """
        Classify text as backchannel or command.
        
        Args:
            text: User utterance to classify
            
        Returns:
            ClassificationResult with decision and confidence
        """
        start = time.perf_counter()
        
        # Use ML if available
        if self._model is not None:
            result = self._classify_ml(text)
            method = "ml"
        else:
            result = self._classify_fallback(text)
            method = "fallback"
        
        processing_time_ms = (time.perf_counter() - start) * 1000
        
        # Update statistics
        self._update_stats(processing_time_ms, method)
        
        return ClassificationResult(
            is_backchannel=result["is_backchannel"],
            confidence=result["confidence"],
            embedding=result.get("embedding"),
            processing_time_ms=processing_time_ms,
            method=method,
        )
    
    def _classify_ml(self, text: str) -> dict:
        """Classify using sentence embeddings."""
        # Get or compute embedding
        text_lower = text.lower().strip()
        
        if self._enable_cache and text_lower in self._embedding_cache:
            embedding = self._embedding_cache[text_lower]
        else:
            embedding = self._model.encode(
                [text],
                convert_to_numpy=True,
                show_progress_bar=False,
            )[0]
            
            if self._enable_cache and len(self._embedding_cache) < 1000:
                self._embedding_cache[text_lower] = embedding
        
        # Compute similarity to backchannel patterns
        backchannel_similarities = self._cosine_similarity(
            embedding,
            self._backchannel_embeddings,
        )
        max_backchannel_sim = np.max(backchannel_similarities)
        
        # Compute similarity to command patterns
        command_similarities = self._cosine_similarity(
            embedding,
            self._command_embeddings,
        )
        max_command_sim = np.max(command_similarities)
        
        # Classify based on which is more similar
        is_backchannel = max_backchannel_sim > max_command_sim
        
        # Confidence is the difference in similarities
        # (larger difference = more confident)
        raw_confidence = abs(max_backchannel_sim - max_command_sim)
        
        # Normalize confidence to 0-1 range
        # If very similar to backchannel pattern, high confidence
        # If similar to both, low confidence
        if is_backchannel:
            confidence = min(1.0, max_backchannel_sim * (1 + raw_confidence))
        else:
            confidence = min(1.0, max_command_sim * (1 + raw_confidence))
        
        logger.debug(
            f"ML classification: '{text}' → "
            f"{'BACKCHANNEL' if is_backchannel else 'COMMAND'} "
            f"(conf={confidence:.3f}, bc_sim={max_backchannel_sim:.3f}, "
            f"cmd_sim={max_command_sim:.3f})"
        )
        
        return {
            "is_backchannel": is_backchannel,
            "confidence": confidence,
            "embedding": embedding,
            "backchannel_similarity": max_backchannel_sim,
            "command_similarity": max_command_sim,
        }
    
    def _classify_fallback(self, text: str) -> dict:
        """Fallback classification using rule-based matching."""
        text_lower = text.lower().strip()
        
        # Check if matches backchannel patterns
        backchannel_matches = sum(
            1 for pattern in self.BACKCHANNEL_PATTERNS
            if pattern in text_lower
        )
        
        # Check if matches command patterns
        command_matches = sum(
            1 for pattern in self.COMMAND_PATTERNS
            if pattern in text_lower
        )
        
        # Classify based on matches
        if backchannel_matches > command_matches:
            is_backchannel = True
            confidence = min(1.0, backchannel_matches / (backchannel_matches + command_matches + 1))
        elif command_matches > backchannel_matches:
            is_backchannel = False
            confidence = min(1.0, command_matches / (backchannel_matches + command_matches + 1))
        else:
            # No clear match, use heuristics
            # Short phrases are typically backchannels
            word_count = len(text_lower.split())
            is_backchannel = word_count <= 2
            confidence = 0.5  # Low confidence
        
        logger.debug(
            f"Fallback classification: '{text}' → "
            f"{'BACKCHANNEL' if is_backchannel else 'COMMAND'} "
            f"(conf={confidence:.3f}, bc={backchannel_matches}, cmd={command_matches})"
        )
        
        return {
            "is_backchannel": is_backchannel,
            "confidence": confidence,
        }
    
    def _cosine_similarity(
        self,
        vec1: np.ndarray,
        vec2_matrix: np.ndarray,
    ) -> np.ndarray:
        """Compute cosine similarity between vector and matrix of vectors."""
        # Normalize vectors
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norms = vec2_matrix / np.linalg.norm(vec2_matrix, axis=1, keepdims=True)
        
        # Compute dot product
        similarities = np.dot(vec2_norms, vec1_norm)
        
        return similarities
    
    def add_backchannel_pattern(self, pattern: str) -> None:
        """
        Add a new backchannel pattern.
        
        Recomputes embeddings if model is loaded.
        """
        if pattern not in self.BACKCHANNEL_PATTERNS:
            self.BACKCHANNEL_PATTERNS.append(pattern)
            
            if self._model is not None:
                # Recompute embeddings
                new_embedding = self._model.encode(
                    [pattern],
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )[0]
                
                self._backchannel_embeddings = np.vstack([
                    self._backchannel_embeddings,
                    new_embedding,
                ])
                
                logger.info(f"Added backchannel pattern: '{pattern}'")
    
    def add_command_pattern(self, pattern: str) -> None:
        """Add a new command pattern."""
        if pattern not in self.COMMAND_PATTERNS:
            self.COMMAND_PATTERNS.append(pattern)
            
            if self._model is not None:
                # Recompute embeddings
                new_embedding = self._model.encode(
                    [pattern],
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )[0]
                
                self._command_embeddings = np.vstack([
                    self._command_embeddings,
                    new_embedding,
                ])
                
                logger.info(f"Added command pattern: '{pattern}'")
    
    def _update_stats(self, processing_time_ms: float, method: str) -> None:
        """Update classification statistics."""
        self._stats["total_classifications"] += 1
        
        if method == "ml":
            self._stats["ml_classifications"] += 1
        else:
            self._stats["fallback_classifications"] += 1
        
        # Running average of processing time
        total = self._stats["total_classifications"]
        prev_avg = self._stats["avg_processing_time_ms"]
        self._stats["avg_processing_time_ms"] = (
            (prev_avg * (total - 1) + processing_time_ms) / total
        )
    
    def get_stats(self) -> dict:
        """Get classifier statistics."""
        stats = self._stats.copy()
        stats["model_loaded"] = self._model is not None
        stats["model_name"] = self._model_name
        stats["cache_size"] = len(self._embedding_cache)
        return stats
    
    @property
    def is_available(self) -> bool:
        """Check if ML classifier is available."""
        return self._model is not None

