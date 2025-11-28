"""
Context Analyzer for Interruption Handler

Analyzes interruption events to determine type, user intent, and optimal response strategy.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger("context-analyzer")


class InterruptionType(Enum):
    """Classification of interruption types"""
    URGENT_QUESTION = "urgent_question"
    CORRECTION = "correction"
    CLARIFICATION = "clarification"
    TOPIC_CHANGE = "topic_change"
    STOP_REQUEST = "stop_request"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    UNKNOWN = "unknown"


class ResumeStrategy(Enum):
    """Agent response strategies for different interruption types"""
    ACKNOWLEDGE_AND_CONTINUE = "acknowledge_continue"
    ACKNOWLEDGE_AND_CHANGE = "acknowledge_change"
    ANSWER_AND_RESUME = "answer_resume"
    RESTART_RESPONSE = "restart"
    STOP_AND_LISTEN = "stop_listen"
    APOLOGIZE_AND_CORRECT = "apologize_correct"


@dataclass
class InterruptionContext:
    """Rich context about an interruption for intelligent decision-making"""
    interruption_type: InterruptionType
    confidence: float  # 0.0 to 1.0
    user_intent: str
    user_utterance: str
    agent_was_saying: str
    agent_topic: str
    recommended_strategy: ResumeStrategy
    reasoning: str
    conversation_history: list[str]
    interruption_point: float  # 0.0-1.0
    
    def __str__(self):
        return (
            f"InterruptionContext(\n"
            f"  Type: {self.interruption_type.value} ({self.confidence:.0%} confident)\n"
            f"  Intent: {self.user_intent}\n"
            f"  User said: '{self.user_utterance}'\n"
            f"  Agent was saying: '{self.agent_was_saying[:50]}...'\n"
            f"  Recommended: {self.recommended_strategy.value}\n"
            f"  Reasoning: {self.reasoning}\n"
            f")"
        )


class ContextAnalyzer:
    """Analyzes interruptions using LLM to determine optimal response strategy"""
    
    def __init__(self, llm):
        self.llm = llm
        logger.info("ContextAnalyzer initialized")
    
    async def analyze_interruption(
        self,
        user_utterance: str,
        agent_speech: str,
        conversation_history: list[str],
        interruption_point: float
    ) -> InterruptionContext:
        """Analyze interruption and determine best response strategy"""
        
        logger.debug(f"Analyzing: user_utterance='{user_utterance}', agent_speech='{agent_speech[:50]}...'")
        
        analysis_prompt = self._build_analysis_prompt(
            user_utterance, agent_speech, conversation_history, interruption_point
        )
        
        try:
            analysis = await self._get_llm_analysis(analysis_prompt)
            context = self._parse_llm_response(
                analysis, user_utterance, agent_speech, 
                conversation_history, interruption_point
            )
            logger.info(f"Interruption analyzed: {context.interruption_type.value}")
            return context
            
        except Exception as e:
            logger.error(f"Error analyzing interruption: {e}")
            return self._get_default_context(
                user_utterance, agent_speech, conversation_history, interruption_point
            )
    
    def _build_analysis_prompt(
        self, user_utterance: str, agent_speech: str, 
        conversation_history: list[str], interruption_point: float
    ) -> str:
        """Build LLM analysis prompt with classification rules"""
        
        history_text = "\n".join(conversation_history[-5:]) if conversation_history else "No prior history"
        
        return f"""Classify this interruption: "{user_utterance}"

CLASSIFICATION RULES:
- "That's interesting", "I see", "Yeah", "Okay", "Right", "Got it", "Mm-hmm" → agreement  
- "Wait!", "Stop!", "Hold on", "Enough" → stop_request
- "What time is it?", "Quick question", "How do I..." → urgent_question  
- "Actually, that's wrong", "No", "That's incorrect" → correction
- "What about X?", "Tell me about Y instead" → topic_change
- "Can you explain?", "I don't understand" → clarification

ANALYZE ONLY: "{user_utterance}"

Context (DO NOT use for classification, only for topic/reasoning):
- Agent was discussing: "{agent_speech}"
- Prior messages: {history_text}

Your task:
1. INTERRUPTION TYPE: Choose ONE from:
   - urgent_question: User has a time-sensitive question
   - correction: User is correcting a mistake
   - clarification: User needs something explained
   - topic_change: User wants to discuss something else
   - stop_request: User wants agent to stop talking
   - agreement: User is agreeing/acknowledging
   - disagreement: User is disagreeing
   - unknown: Cannot determine

2. USER INTENT: In one sentence, what does the user want?

3. AGENT TOPIC: In 2-3 words, what topic was the agent discussing?

4. RECOMMENDED STRATEGY: Choose ONE from:
   - acknowledge_continue: Briefly acknowledge, continue original topic
   - acknowledge_change: Acknowledge and switch to new topic
   - answer_resume: Answer user's question then resume original topic
   - restart: Start the response over from the beginning
   - stop_listen: Stop talking and listen to user
   - apologize_correct: Apologize and correct the mistake

5. REASONING: In one sentence, why this strategy?

6. CONFIDENCE: How confident are you? (low/medium/high)

Respond in this EXACT format:
TYPE: [type]
INTENT: [intent]
TOPIC: [topic]
STRATEGY: [strategy]
REASONING: [reasoning]
CONFIDENCE: [confidence]"""
    
    async def _get_llm_analysis(self, prompt: str) -> str:
        """Get analysis from LLM"""
        if self.llm:
            try:
                from livekit.agents.llm import ChatContext
                
                ctx = ChatContext()
                ctx.add_message(
                    content="You are an expert at analyzing conversation interruptions. Respond in the exact format requested.",
                    role="system"
                )
                ctx.add_message(content=prompt, role="user")
                
                response_text = ""
                async for chunk in self.llm.chat(chat_ctx=ctx).to_str_iterable():
                    response_text += chunk
                
                logger.debug(f"LLM raw response: {response_text[:200]}...")
                return response_text
                
            except Exception as e:
                logger.error(f"LLM analysis failed: {e}")
        
        # Fallback when LLM unavailable
        return """TYPE: stop_request
INTENT: User wants the agent to stop talking
TOPIC: agent capabilities
STRATEGY: stop_listen
REASONING: User explicitly asked to stop, should respect that immediately
CONFIDENCE: high"""
    
    def _parse_llm_response(
        self, llm_response: str, user_utterance: str, agent_speech: str,
        conversation_history: list[str], interruption_point: float
    ) -> InterruptionContext:
        """Parse LLM response into structured InterruptionContext"""
        
        lines = llm_response.strip().split('\n')
        parsed = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                parsed[key.strip().lower()] = value.strip()
        
        # Map to enums with fallbacks
        interruption_type = InterruptionType.UNKNOWN
        try:
            type_str = parsed.get('type', 'unknown')
            interruption_type = InterruptionType(type_str)
        except ValueError:
            logger.warning(f"Unknown interruption type: {type_str}")
        
        resume_strategy = ResumeStrategy.STOP_AND_LISTEN
        try:
            strategy_str = parsed.get('strategy', 'stop_listen')
            resume_strategy = ResumeStrategy(strategy_str)
        except ValueError:
            logger.warning(f"Unknown strategy: {strategy_str}")
        
        confidence_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
        confidence = confidence_map.get(parsed.get('confidence', 'medium').lower(), 0.6)
        
        return InterruptionContext(
            interruption_type=interruption_type,
            confidence=confidence,
            user_intent=parsed.get('intent', 'Unknown intent'),
            user_utterance=user_utterance,
            agent_was_saying=agent_speech,
            agent_topic=parsed.get('topic', 'unknown topic'),
            recommended_strategy=resume_strategy,
            reasoning=parsed.get('reasoning', 'No reasoning provided'),
            conversation_history=conversation_history,
            interruption_point=interruption_point
        )
    
    def _get_default_context(
        self, user_utterance: str, agent_speech: str,
        conversation_history: list[str], interruption_point: float
    ) -> InterruptionContext:
        """Safe fallback when analysis fails"""
        
        return InterruptionContext(
            interruption_type=InterruptionType.UNKNOWN,
            confidence=0.5,
            user_intent="Unable to determine intent",
            user_utterance=user_utterance,
            agent_was_saying=agent_speech,
            agent_topic="unknown",
            recommended_strategy=ResumeStrategy.STOP_AND_LISTEN,
            reasoning="Safe default: stop and listen to user",
            conversation_history=conversation_history,
            interruption_point=interruption_point
        )
