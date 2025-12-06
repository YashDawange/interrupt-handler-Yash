#find mode as per the extractor features

"""
mode_selector.py
----------------
Decides the best interruption-handling strategy:
- RULE
- ML
- LLM
- RAG

Uses Strategy Pattern principles internally. Completely stateless & testable.
"""

from typing import Dict, Any, Literal


Mode = Literal["RULE", "ML", "LLM", "RAG"]


class ModeSelector:
    """
    Single Responsibility:
        Determines the correct mode based on features.
    Open/Closed:
        Add more modes by creating new branches.
    """

    @staticmethod
    def choose(features: Dict[str, Any]) -> Mode:
        """
        Choose best mode based on:
        - message text + length
        - acoustic features (vad, overlap, filler)
        - semantic intent
        - system latency
        - compute availability

        Returns: "RULE" | "ML" | "LLM" | "RAG"
        """

        message: str = features.get("message", "").strip().lower()
        msg_len = len(message.split())

        state: str = features.get("state", "silent")
        vad: int = features.get("vad", 0)
        overlap: int = features.get("overlap", 0)
        filler: int = features.get("filler", 0)
        noise_class: str = features.get("noise_class", "clean")
        semantic_intent: str = features.get("semantic_intent", "unknown")

        latency = features.get("latency_budget", "LOW")  # LOW/MED/HIGH
        compute = features.get("compute_power", "LOW")   # LOW/MID/HIGH

        # ---------------------------------------------------------
        # RULE MODE (fastest, lowest compute)
        # ---------------------------------------------------------
        if latency == "LOW" and compute == "LOW":
            if msg_len <= 3 and filler == 1 and semantic_intent == "ack":
                return "RULE"
            if overlap == 1 and semantic_intent in ["stop", "wait"]:
                return "RULE"

        # ---------------------------------------------------------
        # ML MODE (works with acoustic features)
        # ---------------------------------------------------------
        if overlap in (0, 1) and filler in (0, 1) and noise_class != "unknown":
            if compute in ["LOW", "MID"] and latency in ["LOW", "MED"]:
                return "ML"

        # ---------------------------------------------------------
        # LLM MODE (semantic nuance important)
        # ---------------------------------------------------------
        if msg_len > 3 and semantic_intent not in ["ack", "noise"]:
            if compute == "MID":
                return "LLM"

        # ---------------------------------------------------------
        # RAG MODE (deep reasoning or ambiguity)
        # ---------------------------------------------------------
        if "?" in message or semantic_intent == "ambiguous":
            if compute == "HIGH":
                return "RAG"

        # ---------------------------------------------------------
        # FALLBACK → RULE (safe default)
        # ---------------------------------------------------------
        return "RULE"
