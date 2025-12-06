"""
interruption_manager.py

Dynamic interruption engine that:
1. Uses feature extractors to build a full feature dictionary.
2. Sends features to the ModeSelector.
3. Switches engine at runtime (RULE → ML → LLM → RAG).
4. Executes the chosen engine.
"""

from .factory.engine_factory import EngineFactory
from .factory.llm_factory import LLMFactory

from .engines.rules_engine import RulesEngine
from .engines.llm_engine import LLMEngine
from .engines.rag_engine import RAGEngine
from .engines.ml_engine import MLEngine

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
        self.current_engine_name = "RULE"   # initial/default mode
        self.current_engine = EngineFactory.get_engine(self.current_engine_name)

        # Preload heavy components for performance
        self.overlap_detector = OverlapDetector()
        self.filler_detector = FillerDetector(IGNORE_WORDS)
        self.noise_classifier = NoiseClassifier()
        self.semantic_intent = SemanticIntentClassifier(INTERRUPT_WORDS)

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
    def _extract_features(self, transcript: str, agent_is_speaking: bool, audio_meta: dict):
        """
        Builds unified feature dict to pass to ModeSelector + engines.
        """

        vad = audio_meta.get("vad", 0)
        user_start = audio_meta.get("user_start", 0)
        agent_start = audio_meta.get("agent_start", 0)
        raw_audio = audio_meta.get("audio", None)

        overlap = self.overlap_detector.detect(
            user_start=user_start,
            agent_start=agent_start,
            agent_is_speaking=agent_is_speaking
        )

        filler = self.filler_detector.is_filler(transcript)

        noise_class = self.noise_classifier.classify(raw_audio)

        semantic_intent = self.semantic_intent.classify(transcript)

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
