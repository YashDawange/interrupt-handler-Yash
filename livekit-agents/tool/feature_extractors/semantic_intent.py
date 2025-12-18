# semantic_intent_classifier.py
"""
Rule-first classifier for intent (INTERRUPT / IGNORE / NORMAL).
- Fast deterministic rules handle the majority of cases.
- If ambiguous or confidence low, optional LLM provider is called via the ml_inference wrapper.
"""

from typing import Optional, Dict, Tuple
import re

INTERRUPT_KEYWORDS = ["stop", "wait", "pause", "hold on", "no", "don't", "hang on"]
HIGH_PRIORITY_RE = re.compile(r"\b(?:" + r"|".join(re.escape(x) for x in INTERRUPT_KEYWORDS) + r")\b", flags=re.I)

# Use filler_detector/noise_classifier for pre-processing
from .filler_detector import is_filler_regex
from .noise_classifier import is_noise_by_text

# Optional LLM provider via generic model wrapper
from ..ml_inference.model_wrapper import ModelWrapper  # defined below

class SemanticIntentClassifier:
    def __init__(self, llm_model: Optional[ModelWrapper] = None, llm_conf_threshold: float = 0.7):
        self.llm = llm_model
        self.llm_conf_threshold = llm_conf_threshold

    async def classify(self, transcript: str, agent_is_speaking: bool, features: Dict = None) -> Dict:
        """
        Return dict: {"decision": "INTERRUPT"/"IGNORE"/"NORMAL", "score": float, "meta": {...}}
        Steps:
         1. noise check
         2. filler check
         3. interrupt keyword check
         4. if ambiguous -> call llm_model.predict_sync(...) via wrapper
        """
        meta = {}
        # 1) noise
        is_noise, noise_conf = is_noise_by_text(transcript)
        if is_noise and noise_conf > 0.6:
            return {"decision": "IGNORE", "score": noise_conf, "meta": {"reason": "noise"}}

        # 2) filler/backchannel
        is_filler, filler_conf = is_filler_regex(transcript)
        if agent_is_speaking and is_filler and filler_conf > 0.7:
            return {"decision": "IGNORE", "score": filler_conf, "meta": {"reason": "filler_regex"}}

        # 3) high priority explicit interrupts
        if HIGH_PRIORITY_RE.search(transcript or ""):
            return {"decision": "INTERRUPT", "score": 0.95, "meta": {"reason": "explicit_keyword"}}

        # 4) short exact fillers while silent -> PASSIVE (treated as NORMAL user reply)
        if not agent_is_speaking and is_filler:
            return {"decision": "NORMAL", "score": filler_conf, "meta": {"reason": "filler_while_silent"}}

        # 5) ambiguous / long text -> consult LLM if provided
        # Build a prompt for LLM if available
        if self.llm:
            # synchronous predict helper; wrapper may expose async or sync -> wrapper handles it
            prompt = f"Classify this utterance as INTERRUPT, IGNORE, or NORMAL given agent_is_speaking={agent_is_speaking}. Utterance: {transcript}"
            resp = self.llm.predict(prompt)  # wrapper returns dict {"label":..., "score":...} or string
            if isinstance(resp, dict):
                lbl = resp.get("label")
                sc = float(resp.get("score", 0.0))
                # map LLM labels (be flexible)
                if lbl and lbl.upper() in ("INTERRUPT", "IGNORE", "NORMAL", "PASSIVE"):
                    mapped = "NORMAL" if lbl.upper()=="PASSIVE" else lbl.upper()
                    # enforce threshold
                    if sc >= self.llm_conf_threshold:
                        return {"decision": mapped, "score": sc, "meta": {"reason": "llm_confident", "raw": resp}}
                    else:
                        return {"decision": mapped, "score": sc, "meta": {"reason": "llm_low_conf", "raw": resp}}
            elif isinstance(resp, str):
                txt = resp.strip().upper()
                # quick parse
                for label in ("INTERRUPT","IGNORE","NORMAL","PASSIVE"):
                    if label in txt:
                        mapped = "NORMAL" if label=="PASSIVE" else label
                        return {"decision": mapped, "score": 0.6, "meta": {"reason": "llm_text"}}
        # 6) fallback default
        return {"decision": "NORMAL", "score": 0.3, "meta": {"reason": "fallback"}}

# Example usage (sync):
# from livekit_agents.feature_extractors.semantic_intent_classifier import SemanticIntentClassifier
# cls = SemanticIntentClassifier()
# print(asyncio.run(cls.classify("yeah ok", agent_is_speaking=True)))
