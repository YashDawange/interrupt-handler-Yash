#factory/engine_factory.py
from ..config import *
from ..engines.rules_engine import RulesEngine
from ..engines.llm_engine import LLMEngine
from ..engines.ml_engine import MLEngine
from ..engines.rag_engine import RAGEngine

class EngineFactory:
    @staticmethod
    def get_engine(mode: str):
        if mode == "RULES":
            return RulesEngine(IGNORE_WORDS, INTERRUPT_WORDS)
        elif mode == "LLM":
            return LLMEngine(LLM_PROVIDER_NAME, LLM_MODEL_NAME)
        elif mode == "ML":
            return MLEngine(ML_MODEL_PATH)
        elif mode == "RAG": 
                    return RAGEngine(RAG_LLM_PROVIDER_NAME, RAG_LLM_MODEL_NAME)        
        elif mode == "HYBRID":
            # For Hybrid, we return the Rules engine as primary, 
            # manager handles the fallback logic.
            return RulesEngine(IGNORE_WORDS, INTERRUPT_WORDS)
        else:
            raise ValueError(f"Unknown Mode: {mode}")