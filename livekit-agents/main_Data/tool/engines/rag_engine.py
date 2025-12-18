# engines/rag_engine.py
from .base_engine import BaseEngine
from ..factory.llm_factory import LLMFactory
from ..rag.rag_retriver import RAGRetriever
from ..config import RAG_VECTOR_STORE_PATH, RAG_K_CONTEXT
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import logging

class RAGEngine(BaseEngine):
    def __init__(self, provider_name: str, model_name: str):
        self.logger = logging.getLogger("RAGEngine")
        self.llm = LLMFactory.create(provider_name, model_name)
        
        # Initialize Retriever
        self.retriever = RAGRetriever(
            db_path=RAG_VECTOR_STORE_PATH, 
            llm_model_name=model_name
        )
        
        # Define Prompt Template for RAG
        self.prompt = ChatPromptTemplate.from_template(
            """
            You are a conversational flow controller. Your task is to analyze a USER INPUT 
            in the context of the AGENT STATE and a set of **Interruption Rules (Context)**.

            Use the provided context to decide if the user's utterance is an INTERRUPT, 
            an IGNORE backchannel, or a NORMAL conversational turn. 
            If the context is irrelevant, rely on common sense.

            Valid Decisions: INTERRUPT, IGNORE, NORMAL.

            --- CONTEXTUAL RULES ---
            {docs}
            ---

            Agent State: {agent_state}
            User Input: "{transcript}"
            
            Return JSON only: {{ "decision": "...", "score": 0.0-1.0, "reason": "RAG-based decision" }}
            """
        )
        self.parser = JsonOutputParser()

    async def classify(self, transcript: str, agent_is_speaking: bool, context: dict = None) -> dict:
        state = "SPEAKING" if agent_is_speaking else "SILENT"
        
        try:
            # 1. Retrieval Step: Get the most relevant interruption rules
            docs = await self.retriever.get_relevant_context(
                query=transcript, 
                k=RAG_K_CONTEXT
            )

            # 2. Generation Step: Pass context and user query to LLM
            prompt_input = {
                "agent_state": state,
                "transcript": transcript,
                "docs": docs
            }
            
            chain = self.prompt | self.llm | self.parser
            
            result = await chain.ainvoke(prompt_input)
            
            return {
                "decision": result.get("decision", "NORMAL"),
                "score": result.get("score", 0.0),
                "reason": result.get("reason", "RAG-inference")
            }
            
        except Exception as e:
            self.logger.error(f"RAG Engine failure: {e}")
            # Fallback to NORMAL to avoid freezing the conversation
            return {"decision": "NORMAL", "score": 0.0, "reason": "rag_error_fallback"}