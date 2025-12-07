"""
interruption_manager.py

Dynamic interruption engine that:
1. Uses feature extractors to build a full feature dictionary.
2. Sends features to the ModeSelector.
3. Switches engine at runtime (RULE → ML → LLM → RAG).
4. Executes the chosen engine.
"""
import asyncio
from typing import Dict, Tuple, List, Any
from .factory.engine_factory import EngineFactory
from .feature_extractors.overlap_detector import OverlapDetector
from .feature_extractors.filler_detector import FillerDetector
from .feature_extractors.noise_classifier import NoiseClassifier
from .feature_extractors.semantic_intent import SemanticIntentClassifier

from .utils.mode_selector import ModeSelector
from .config import (
    IGNORE_WORDS,
    INTERRUPT_WORDS,
    LLM_PROVIDER_NAME,
    LLM_MODEL_NAME,
    LATENCY_BUDGET,
    COMPUTE_POWER
)


class InterruptionManager:
    def __init__(self):
        self.current_engine_name = "RULES"   # initial/default mode
        self.current_engine = EngineFactory.get_engine(self.current_engine_name)

        # Preload heavy components for performance
        self.overlap_detector = OverlapDetector()
        self.filler_detector = FillerDetector(IGNORE_WORDS)
        self.noise_classifier = NoiseClassifier()
        self.semantic_intent = SemanticIntentClassifier() 

    async def analyze(self, transcript: str, agent_is_speaking: bool, audio_meta: dict) -> str:
        """
        Main entry point called on every transcript chunk.
        audio_meta contains:
            - user_start_time
            - agent_start_time
            - vad_flag
            - raw signal if needed
        """

        # ------------------------------------------------------------------
        # 1. EXTRACT FEATURES
        # ------------------------------------------------------------------
        features = self._extract_features(
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
        result = await self.current_engine.classify(
            transcript,
            agent_is_speaking,
            features
        )

        return result["decision"]

    # ----------------------------------------------------------------------
    # Feature extraction
    # ----------------------------------------------------------------------
    async def _extract_features(self, transcript: str, agent_is_speaking: bool, audio_meta: dict):
        """
        Builds unified feature dict to pass to ModeSelector + engines.
        """

        vad = audio_meta.get("vad", 0)
        user_start = audio_meta.get("user_start", 0)
        agent_start = audio_meta.get("agent_start", 0)
        raw_audio = audio_meta.get("audio", None)
        raw_audio_rms = audio_meta.get("rms", 0.0)

        overlap = self.overlap_detector.detect(
            user_start=user_start,
            agent_start=agent_start,
            agent_is_speaking=agent_is_speaking
        )

        is_filler, filler_conf = self.filler_detector.is_filler_hybrid_nltk(transcript)
        filler = {"is_filler": is_filler, "confidence": filler_conf}

        is_noise_trans, noise_conf_trans = self.noise_classifier.is_noise_hybrid_nltk(transcript)
        is_noise_rms, noise_conf_rms = self.noise_classifier.is_noise_by_energy(raw_audio_rms)
        
        # Prioritize the higher confidence score (transcript or energy)
        if noise_conf_rms > noise_conf_trans:
            noise_class = {"is_noise": is_noise_rms, "confidence": noise_conf_rms, "source": "rms"}
        else:
            noise_class = {"is_noise": is_noise_trans, "confidence": noise_conf_trans, "source": "transcript"}


        semantic_intent = await self.semantic_intent.classify( # Retaining await for safety
            transcript, 
            agent_is_speaking, 
            features={"filler": filler, "noise_class": noise_class} # passing necessary features
        )

        # build final features dict
        return {
            "message": transcript,
            "state": "speaking" if agent_is_speaking else "silent",
            "vad": vad,
            "overlap": overlap,
            "filler": filler,
            "noise_class": noise_class,
            "semantic_intent": semantic_intent,

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