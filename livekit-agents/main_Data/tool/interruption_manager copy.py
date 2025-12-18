"""
interruption_manager.py - IMPROVISED

Dynamic interruption engine that:
1. Uses feature extractors with correct, NLTK-integrated signatures.
2. Sends features to the ModeSelector.
3. Switches engine at runtime (RULE → ML → LLM → RAG).
4. Executes the chosen engine.
"""
import asyncio
from typing import Dict, Tuple, List, Any

# --- IMPORTS FOR DEMONSTRATION/REFACTORING ---
# In a real setup, these would be the relative imports you had.
# We import the classes and functions directly from your provided modules
# (assuming the other files are available or we use the defined classes/functions).

# Refactored Imports to use the provided class definitions
from filler_detector import FillerDetector, DEFAULT_FILLERS
from noise_classifier import NoiseClassifier
from semantic_intent import SemanticIntentClassifier, INTERRUPT_KEYWORDS

# Placeholder imports for components not provided (Engine/Factory/Selector)
# NOTE: The implementation below ASSUMES these placeholders work as expected.
class OverlapDetector:
    def detect(self, user_start, agent_start, agent_is_speaking): return 0.5 # Mock
class RulesEngine:
    async def classify(self, transcript, agent_is_speaking, features): return {"decision": "NORMAL"}
class EngineFactory:
    @staticmethod
    def get_engine(name): return RulesEngine() # Simplified Mock
class ModeSelector:
    @staticmethod
    def choose(features): return "RULES" # Simplified Mock

# Placeholder Config variables
IGNORE_WORDS = DEFAULT_FILLERS 
INTERRUPT_WORDS = INTERRUPT_KEYWORDS
LATENCY_BUDGET = 200 # ms
COMPUTE_POWER = 8 # cores

# We remove LLMFactory and specific Engine imports as they are now handled by EngineFactory mock.

class InterruptionManager:
    """
    Manages the overall interruption workflow, from feature extraction to engine classification.
    """
    def __init__(self):
        # Initializing the engine with the factory (mocked)
        self.current_engine_name = "RULES"
        self.current_engine = EngineFactory.get_engine(self.current_engine_name)

        # Preload feature extractors with correct, updated configurations
        self.overlap_detector = OverlapDetector()

        # CORRECTED: Initialized with a set of fillers, matching the __init__ signature
        self.filler_detector = FillerDetector(fillers=IGNORE_WORDS) 
        
        # CORRECTED: Initialized the NoiseClassifier
        self.noise_classifier = NoiseClassifier()
        
        # CORRECTED: SemanticIntentClassifier is initialized without args based on its source code
        self.semantic_intent = SemanticIntentClassifier() 

    async def analyze(self, transcript: str, agent_is_speaking: bool, audio_meta: dict) -> str:
        """
        Main entry point called on every transcript chunk.
        """

        # ------------------------------------------------------------------
        # 1. EXTRACT FEATURES
        # ------------------------------------------------------------------
        features = await self._extract_features( # Made async to handle SemanticIntent call
            transcript=transcript,
            agent_is_speaking=agent_is_speaking,
            audio_meta=audio_meta
        )

        # ------------------------------------------------------------------
        # 2. CHOOSE BEST MODE DYNAMICALLY
        # ------------------------------------------------------------------
        new_mode = ModeSelector.choose(features)

        # Switch engine if mode changed
        if new_mode != self.current_engine_name:
            self.current_engine_name = new_mode
            self.current_engine = EngineFactory.get_engine(self.current_engine_name)

        # ------------------------------------------------------------------
        # 3. RUN SELECTED ENGINE
        # ------------------------------------------------------------------
        # Await the engine's classification
        result = await self.current_engine.classify(
            transcript,
            agent_is_speaking,
            features
        )

        return result["decision"]

    # ----------------------------------------------------------------------
    # Feature extraction - NOW ASYNC TO ALIGN WITH CLASSIFIER SIGNATURE
    # ----------------------------------------------------------------------
    async def _extract_features(self, transcript: str, agent_is_speaking: bool, audio_meta: dict) -> Dict[str, Any]:
        """
        Builds unified feature dict to pass to ModeSelector + engines,
        using the correct signatures of the hybrid detectors.
        """

        vad = audio_meta.get("vad", 0)
        user_start = audio_meta.get("user_start", 0)
        agent_start = audio_meta.get("agent_start", 0)
        # Note: raw_audio is needed for is_noise_by_energy, but the Manager
        # was only passing it to a general 'classify' in the original.
        raw_audio_rms = audio_meta.get("rms", 0.0)

        overlap = self.overlap_detector.detect(
            user_start=user_start,
            agent_start=agent_start,
            agent_is_speaking=agent_is_speaking
        )

        # CORRECTED: Use the NLTK-integrated hybrid method. Returns (bool, float)
        is_filler, filler_conf = self.filler_detector.is_filler_hybrid_nltk(transcript)
        filler = {"is_filler": is_filler, "confidence": filler_conf}

        # CORRECTED: We now need to decide if we classify by transcript or by energy.
        # For simplicity, we check transcript first, then fall back to energy check confidence.
        is_noise_trans, noise_conf_trans = self.noise_classifier.is_noise_hybrid_nltk(transcript)
        is_noise_rms, noise_conf_rms = self.noise_classifier.is_noise_by_energy(raw_audio_rms)
        
        # Prioritize the higher confidence score (transcript or energy)
        if noise_conf_rms > noise_conf_trans:
            noise_class = {"is_noise": is_noise_rms, "confidence": noise_conf_rms, "source": "rms"}
        else:
            noise_class = {"is_noise": is_noise_trans, "confidence": noise_conf_trans, "source": "transcript"}


        # CORRECTED: Call the classifier's async method (even if mocked/simplified)
        # Since the SemanticIntentClassifier was made LLM-free, we can call it synchronously.
        # But we keep it as 'await' in the manager if the signature demands it, or simplify.
        # Let's simplify the call to synchronous, as the provided SemanticIntentClassifier's 
        # classify method has no 'await' calls inside, making it effectively sync.
        # The mock wrapper for `if __name__ == "__main__"` also implies synchronous usage.
        semantic_intent = await self.semantic_intent.classify( # Retaining await for safety
            transcript, 
            agent_is_speaking, 
            features={"filler": filler, "noise_class": noise_class} # passing necessary features
        )
        # semantic_intent is now a dict: {"decision": "...", "score": ...}

        # build final features dict
        return {
            "message": transcript,
            "state": "speaking" if agent_is_speaking else "silent",
            "vad": vad,
            "overlap": overlap,
            "filler": filler, # Now a dict
            "noise_class": noise_class, # Now a dict
            "semantic_intent": semantic_intent, # Now a dict

            # system/env constraints
            "latency_budget": LATENCY_BUDGET,
            "compute_power": COMPUTE_POWER,
        }

if __name__ == "__main__":
    async def main():
        print("--- Testing Improvised InterruptionManager ---")
        manager = InterruptionManager()
        
        # Mock Data (based on test cases from the other files)
        test_cases = [
            ("stop the music now!", True, 0.001), # Explicit Interrupt
            ("yeah ok", True, 0.00001), # Filler/Backchannel + Low RMS (Ignore)
            ("I hear some wind noise", True, 0.001), # Noise
            ("I'm asking about the price", True, 0.001), # Normal
        ]
        
        for transcript, agent_speaking, rms in test_cases:
            audio_meta = {
                "vad": 1,
                "user_start": 100,
                "agent_start": 98,
                "rms": rms,
            }
            decision = await manager.analyze(transcript, agent_speaking, audio_meta)
            print(f"Transcript: '{transcript}' (Agent Speaking: {agent_speaking})")
            print(f"  -> FINAL DECISION: **{decision}** (Current Engine: {manager.current_engine_name})")

    # Run the test
    asyncio.run(main())