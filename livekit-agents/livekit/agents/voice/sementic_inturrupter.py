"""
Semantic-based interruption classifier using sentence embeddings.
This replaces keyword matching with ML-based intent classification.
"""

from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)


class SemanticInterruptClassifier:
    """
    Classifies user utterances using semantic embeddings instead of keyword matching.
    
    Categories:
    - 'backchannel': Acknowledgments that shouldn't interrupt (yeah, okay, uh-huh)
    - 'interrupt': Real interruptions that should stop the agent (wait, stop, no)
    """
    
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        """
        Initialize the classifier.
        
        Args:
            model_name: Sentence transformer model to use
                       'all-MiniLM-L6-v2' - Fast, 80MB, good balance
                       'all-mpnet-base-v2' - More accurate, 420MB, slower
        """
        logger.info(f"Loading semantic model: {model_name}")
        self.model = SentenceTransformer(model_name)
        
        # Training examples for each category
        self.training_data = {
            'backchannel': [
                # Simple acknowledgments
                "yeah", "yes", "yep", "yup", "uh-huh", "uh huh",
                "okay", "ok", "alright", "sure", "right",
                "hmm", "mhm", "mm-hmm",
                
                # Positive reactions
                "cool", "nice", "great", "awesome", "good",
                "i see", "got it", "gotcha", "understood",
                "makes sense", "that's interesting", "i understand",
                
                # Agreement phrases
                "yeah exactly", "okay cool", "right right",
                "yes i agree", "that makes sense",
                "i'm following", "keep going", "go on",
            ],
            
            'interrupt': [
                # Stop commands
                "wait", "stop", "hold on", "hold up", "hang on",
                "pause", "wait a second", "wait a minute",
                "one moment", "just a second",
                
                # Disagreement
                "no", "not really", "i don't think so", "i disagree",
                "that's not right", "that's wrong", "actually no",
                "i don't agree", "but", "however",
                
                # Questions (need clarification)
                "what?", "huh?", "what do you mean?",
                "can you repeat that?", "can you explain?",
                "what did you say?", "sorry what?",
                
                # Corrections
                "actually", "correction", "let me stop you",
                "i need to say something", "i have a question",
                "can i ask something?", "before you continue",
                
                # Strong interjections
                "excuse me", "sorry to interrupt", "one thing",
                "i want to add", "i have to say",
            ]
        }
        
        # Compute prototype embeddings
        logger.info("Computing prototype embeddings...")
        self._compute_prototypes()
        
        logger.info(f"Classifier initialized with {len(self.backchannel_examples)} backchannel "
                   f"and {len(self.interrupt_examples)} interrupt examples")
    
    def _compute_prototypes(self):
        """Compute average embeddings for each category."""
        # Get all examples
        self.backchannel_examples = self.training_data['backchannel']
        self.interrupt_examples = self.training_data['interrupt']
        
        # Encode examples
        backchannel_embeddings = self.model.encode(self.backchannel_examples)
        interrupt_embeddings = self.model.encode(self.interrupt_examples)
        
        # Compute centroids (prototype vectors)
        self.backchannel_prototype = np.mean(backchannel_embeddings, axis=0)
        self.interrupt_prototype = np.mean(interrupt_embeddings, axis=0)
        
        # Also store individual embeddings for nearest-neighbor fallback
        self.backchannel_embeddings = backchannel_embeddings
        self.interrupt_embeddings = interrupt_embeddings
    
    def classify(self, text: str, return_confidence: bool = False):
        """
        Classify user input as 'backchannel' or 'interrupt'.
        
        Args:
            text: User's utterance
            return_confidence: If True, return (label, confidence) tuple
            
        Returns:
            'backchannel', 'interrupt', or ('label', confidence_score)
        """
        if not text or not text.strip():
            return ('interrupt', 0.5) if return_confidence else 'interrupt'
        
        # Encode the input text
        text_embedding = self.model.encode([text.lower().strip()])[0]
        
        # Compute similarity to prototypes
        backchannel_sim = cosine_similarity(
            [text_embedding], 
            [self.backchannel_prototype]
        )[0][0]
        
        interrupt_sim = cosine_similarity(
            [text_embedding], 
            [self.interrupt_prototype]
        )[0][0]
        
        logger.debug(f"Text: '{text}' | Backchannel sim: {backchannel_sim:.3f} | "
                    f"Interrupt sim: {interrupt_sim:.3f}")
        
        # Decision logic with tuned thresholds
        if backchannel_sim > 0.75:  # High confidence backchannel
            result = 'backchannel'
            confidence = backchannel_sim
        elif interrupt_sim > 0.65:  # High confidence interrupt
            result = 'interrupt'
            confidence = interrupt_sim
        elif backchannel_sim > interrupt_sim:
            # Closer to backchannel but not confident
            result = 'backchannel'
            confidence = backchannel_sim
        else:
            # Default to interrupt (safer - won't ignore real interruptions)
            result = 'interrupt'
            confidence = interrupt_sim
        
        if return_confidence:
            return (result, confidence)
        return result
    
    def classify_with_nearest_neighbor(self, text: str, k: int = 3):
        """
        Alternative classification using k-nearest neighbors.
        More accurate but slightly slower (~10ms more).
        """
        text_embedding = self.model.encode([text.lower().strip()])[0]
        
        # Find k nearest neighbors in backchannel examples
        backchannel_sims = cosine_similarity(
            [text_embedding], 
            self.backchannel_embeddings
        )[0]
        top_backchannel_sims = np.sort(backchannel_sims)[-k:]
        
        # Find k nearest neighbors in interrupt examples
        interrupt_sims = cosine_similarity(
            [text_embedding], 
            self.interrupt_embeddings
        )[0]
        top_interrupt_sims = np.sort(interrupt_sims)[-k:]
        
        # Average of top-k similarities
        avg_backchannel = np.mean(top_backchannel_sims)
        avg_interrupt = np.mean(top_interrupt_sims)
        
        logger.debug(f"KNN: Text '{text}' | Avg backchannel: {avg_backchannel:.3f} | "
                    f"Avg interrupt: {avg_interrupt:.3f}")
        
        if avg_backchannel > avg_interrupt:
            return ('backchannel', avg_backchannel)
        else:
            return ('interrupt', avg_interrupt)
    
    def add_training_example(self, text: str, label: str):
        """
        Add a new training example and recompute prototypes.
        Useful for online learning from user corrections.
        
        Args:
            text: Example utterance
            label: 'backchannel' or 'interrupt'
        """
        if label not in self.training_data:
            raise ValueError(f"Label must be 'backchannel' or 'interrupt', got '{label}'")
        
        self.training_data[label].append(text)
        self._compute_prototypes()
        logger.info(f"Added training example: '{text}' -> {label}")


# Global classifier instance (lazy loaded)
_classifier_instance = None


def get_classifier(force_reload: bool = False):
    """
    Get or create the global classifier instance.
    
    Args:
        force_reload: Force reload the model from scratch
        
    Returns:
        SemanticInterruptClassifier instance
    """
    global _classifier_instance
    
    if _classifier_instance is None or force_reload:
        _classifier_instance = SemanticInterruptClassifier()
    
    return _classifier_instance


# Convenience functions for direct use
def classify_utterance(text: str) -> str:
    """Quick classification function."""
    classifier = get_classifier()
    return classifier.classify(text)


def classify_with_confidence(text: str) -> tuple:
    """Classification with confidence score."""
    classifier = get_classifier()
    return classifier.classify(text, return_confidence=True)


# ============================================================================
# Testing & Benchmarking
# ============================================================================

def test_classifier():
    """Test the classifier with various examples."""
    print("="*60)
    print("Testing Semantic Interrupt Classifier")
    print("="*60)
    
    classifier = get_classifier()
    
    test_cases = [
        # Should be backchannel
        ("yeah", "backchannel"),
        ("okay cool", "backchannel"),
        ("i see what you mean", "backchannel"),
        ("that's interesting", "backchannel"),
        ("mm-hmm", "backchannel"),
        
        # Should be interrupt
        ("wait a second", "interrupt"),
        ("no that's wrong", "interrupt"),
        ("i disagree", "interrupt"),
        ("can you repeat that?", "interrupt"),
        ("hold on", "interrupt"),
        
        # Edge cases
        ("yeah but wait", "interrupt"),  # Mixed
        ("okay i have a question", "interrupt"),  # Starts as backchannel
        ("nope", "interrupt"),
        ("yup got it", "backchannel"),
    ]
    
    correct = 0
    for text, expected in test_cases:
        result, confidence = classifier.classify(text, return_confidence=True)
        is_correct = result == expected
        correct += is_correct
        
        status = "✅" if is_correct else "❌"
        print(f"{status} '{text:30s}' -> {result:12s} (conf: {confidence:.2f}) "
              f"[expected: {expected}]")
    
    accuracy = correct / len(test_cases) * 100
    print(f"\n{'='*60}")
    print(f"Accuracy: {correct}/{len(test_cases)} = {accuracy:.1f}%")
    print(f"{'='*60}")


def benchmark_latency():
    """Benchmark classification speed."""
    import time
    
    classifier = get_classifier()
    
    test_texts = [
        "yeah", "okay", "wait", "no", "i disagree",
        "that's interesting", "hold on a second"
    ]
    
    # Warmup
    for text in test_texts:
        classifier.classify(text)
    
    # Benchmark
    n_iterations = 100
    start = time.time()
    
    for _ in range(n_iterations):
        for text in test_texts:
            classifier.classify(text)
    
    elapsed = time.time() - start
    avg_latency = (elapsed / (n_iterations * len(test_texts))) * 1000
    
    print(f"\n{'='*60}")
    print(f"Latency Benchmark")
    print(f"{'='*60}")
    print(f"Average latency: {avg_latency:.2f}ms per classification")
    print(f"Total time: {elapsed:.2f}s for {n_iterations * len(test_texts)} classifications")
    print(f"{'='*60}")


if __name__ == "__main__":
    # Run tests
    test_classifier()
    benchmark_latency()