from .base_engine import BaseEngine
from ..factory.llm_factory import LLMFactory
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import logging

class LLMEngine(BaseEngine):
    def __init__(self, provider_name, model_name):
        self.llm = LLMFactory.create(provider_name, model_name)
        self.logger = logging.getLogger("LLMEngine")
        
        # Define Prompt
        self.prompt = ChatPromptTemplate.from_template(
            """
            You are a conversational flow controller.
            Analyze the USER INPUT relative to the AGENT STATE.
            
            Valid Decisions:
            - INTERRUPT: User clearly wants to stop the agent or change topic ("stop", "wait", "no").
            - IGNORE: User is just backchanneling ("yeah", "uh-huh") while agent speaks.
            - NORMAL: Regular conversation turn.

            Agent State: {agent_state}
            User Input: "{transcript}"
            
            Return JSON only: {{ "decision": "...", "score": 0.0-1.0 }}
            """
        )
        self.chain = self.prompt | self.llm | JsonOutputParser()

    async def classify(self, transcript: str, agent_is_speaking: bool, context: dict = None) -> dict:
        state = "SPEAKING" if agent_is_speaking else "SILENT"
        try:
            # Async invocation of LangChain
            result = await self.chain.ainvoke({"agent_state": state, "transcript": transcript})
            return {"decision": result.get("decision", "NORMAL"), "score": result.get("score", 0.0), "reason": "llm_inference"}
        except Exception as e:
            self.logger.error(f"LLM fail: {e}")
            return {"decision": "NORMAL", "score": 0.0, "reason": "llm_error_fallback"}