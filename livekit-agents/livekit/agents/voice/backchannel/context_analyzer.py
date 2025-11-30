"""
Context-Aware Backchannel Analysis

Analyzes conversation context to make smarter interruption decisions:
- Considers agent's recent utterances
- Detects negation patterns ("don't stop")
- Analyzes sentence structure
- Checks conversation flow
- Uses LLM for ambiguous cases (optional)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ....log import logger

if TYPE_CHECKING:
    from ....llm import ChatContext, LLM


@dataclass
class ContextFeatures:
    """
    Features extracted from conversation context.
    """
    
    # Agent state
    agent_utterance_duration: float | None  # How long agent has been speaking
    agent_asked_question: bool  # Did agent just ask a question?
    agent_utterance_length: int  # Word count of current agent utterance
    
    # User input analysis
    has_negation: bool  # Contains "don't", "not", etc.
    is_mid_sentence: bool  # User interrupted mid-word
    after_silence: bool  # User spoke after a pause
    
    # Conversation flow
    turns_since_user_spoke: int  # How many agent turns since user's last input
    conversation_topic: str | None  # Current topic if detectable
    
    # Timing
    time_since_agent_started_speaking: float | None
    time_since_user_last_spoke: float | None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "agent_utterance_duration": self.agent_utterance_duration,
            "agent_asked_question": self.agent_asked_question,
            "has_negation": self.has_negation,
            "after_silence": self.after_silence,
            "turns_since_user_spoke": self.turns_since_user_spoke,
        }


class ContextAnalyzer:
    """
    Analyzes conversation context for better backchannel detection.
    
    Uses rule-based heuristics and optional LLM disambiguation.
    """
    
    # Negation patterns (multi-language)
    NEGATION_PATTERNS = [
        # English
        r"\bdon't\b", r"\bdont\b", r"\bdo not\b", r"\bnot\b", r"\bno\b",
        r"\bnever\b", r"\bnobody\b", r"\bnothing\b", r"\bneither\b",
        # Spanish
        r"\bno\b", r"\bnunca\b", r"\bnada\b", r"\bnadie\b",
        # French
        r"\bne\b", r"\bpas\b", r"\bjamais\b", r"\brien\b",
        # German
        r"\bnicht\b", r"\bkein\b", r"\bnie\b", r"\bniemals\b",
    ]
    
    # Question patterns
    QUESTION_PATTERNS = [
        r"\?$",  # Ends with question mark
        # English
        r"^\s*(what|why|how|when|where|who|which|can|could|would|should|do|does|did|is|are|was|were)",
        # Spanish
        r"^\s*(qué|por qué|cómo|cuándo|dónde|quién|puedes|podrías)",
        # French
        r"^\s*(qu'|quel|pourquoi|comment|quand|où|qui|peux|pourrais)",
        # German
        r"^\s*(was|warum|wie|wann|wo|wer|kannst|könntest)",
    ]
    
    def __init__(
        self,
        *,
        enable_llm_disambiguation: bool = False,
        llm: LLM | None = None,
    ):
        """
        Initialize context analyzer.
        
        Args:
            enable_llm_disambiguation: Whether to use LLM for ambiguous cases
            llm: LLM instance for disambiguation (if enabled)
        """
        self._enable_llm = enable_llm_disambiguation
        self._llm = llm
        
        # Compile regex patterns
        self._negation_regex = re.compile(
            "|".join(self.NEGATION_PATTERNS),
            re.IGNORECASE,
        )
        self._question_regex = re.compile(
            "|".join(self.QUESTION_PATTERNS),
            re.IGNORECASE,
        )
        
        # Track conversation state
        self._agent_speaking_start_time: float | None = None
        self._user_last_spoke_time: float | None = None
        self._agent_turn_count = 0
        self._current_agent_utterance = ""
        
        logger.info(
            f"ContextAnalyzer initialized: "
            f"llm_disambiguation={enable_llm_disambiguation}"
        )
    
    def extract_features(
        self,
        transcript: str,
        *,
        agent_speaking: bool,
        agent_utterance: str | None = None,
        chat_ctx: ChatContext | None = None,
    ) -> ContextFeatures:
        """
        Extract context features from current situation.
        
        Args:
            transcript: User's transcribed text
            agent_speaking: Whether agent is currently speaking
            agent_utterance: Agent's current utterance if available
            chat_ctx: Full conversation context if available
            
        Returns:
            ContextFeatures object
        """
        # Agent utterance analysis
        agent_utterance_duration = None
        agent_utterance_length = 0
        agent_asked_question = False
        
        if agent_speaking and agent_utterance:
            self._current_agent_utterance = agent_utterance
            agent_utterance_length = len(agent_utterance.split())
            agent_asked_question = self._is_question(agent_utterance)
            
            if self._agent_speaking_start_time:
                agent_utterance_duration = (
                    time.time() - self._agent_speaking_start_time
                )
        
        # User input analysis
        has_negation = self._has_negation(transcript)
        is_mid_sentence = self._is_mid_sentence(transcript)
        after_silence = self._is_after_silence()
        
        # Timing
        time_since_agent_started = (
            time.time() - self._agent_speaking_start_time
            if self._agent_speaking_start_time
            else None
        )
        time_since_user_last = (
            time.time() - self._user_last_spoke_time
            if self._user_last_spoke_time
            else None
        )
        
        # Conversation history analysis
        turns_since_user_spoke = self._get_turns_since_user_spoke(chat_ctx)
        
        return ContextFeatures(
            agent_utterance_duration=agent_utterance_duration,
            agent_asked_question=agent_asked_question,
            agent_utterance_length=agent_utterance_length,
            has_negation=has_negation,
            is_mid_sentence=is_mid_sentence,
            after_silence=after_silence,
            turns_since_user_spoke=turns_since_user_spoke,
            conversation_topic=None,  # TODO: Topic extraction
            time_since_agent_started_speaking=time_since_agent_started,
            time_since_user_last_spoke=time_since_user_last,
        )
    
    def compute_context_score(
        self,
        transcript: str,
        features: ContextFeatures,
        agent_speaking: bool,
    ) -> float:
        """
        Compute backchannel likelihood from context (0-1).
        
        Higher score = more likely to be backchannel.
        
        Args:
            transcript: User's input
            features: Extracted context features
            agent_speaking: Whether agent is speaking
            
        Returns:
            Context score 0-1
        """
        score = 0.5  # Start neutral
        
        # If agent is speaking for a long time, more likely user is backchanneling
        if features.agent_utterance_duration:
            if features.agent_utterance_duration > 5.0:
                score += 0.15
            if features.agent_utterance_duration > 10.0:
                score += 0.10
        
        # If agent asked a question, less likely to be backchannel
        # (user is probably answering)
        if features.agent_asked_question:
            score -= 0.20
        
        # If input contains negation, might be "don't stop" (not interruption)
        if features.has_negation:
            score += 0.10
        
        # If after silence, more likely to be command (deliberate input)
        if features.after_silence:
            score -= 0.15
        
        # If agent has been dominating conversation, more likely backchannel
        if features.turns_since_user_spoke >= 3:
            score += 0.10
        
        # If user interrupted mid-sentence, less likely backchannel
        if features.is_mid_sentence:
            score -= 0.10
        
        # Long agent utterances suggest explanation mode (backchannels likely)
        if features.agent_utterance_length > 30:
            score += 0.10
        
        return max(0.0, min(1.0, score))
    
    async def disambiguate_with_llm(
        self,
        transcript: str,
        context: ChatContext,
    ) -> tuple[bool, float]:
        """
        Use LLM to disambiguate ambiguous cases.
        
        Args:
            transcript: User's input
            context: Conversation context
            
        Returns:
            Tuple of (is_backchannel, confidence)
        """
        if not self._enable_llm or not self._llm:
            return (False, 0.5)  # Neutral if LLM not available
        
        try:
            # Construct prompt for LLM
            prompt = self._build_disambiguation_prompt(transcript, context)
            
            # Query LLM
            response = await self._llm.chat(prompt)
            
            # Parse response (expecting "backchannel" or "command")
            response_lower = response.lower().strip()
            
            if "backchannel" in response_lower:
                return (True, 0.8)
            elif "command" in response_lower or "interrupt" in response_lower:
                return (False, 0.8)
            else:
                return (False, 0.5)  # Uncertain
                
        except Exception as e:
            logger.warning(f"LLM disambiguation failed: {e}")
            return (False, 0.5)
    
    def _build_disambiguation_prompt(
        self,
        transcript: str,
        context: ChatContext,
    ) -> str:
        """Build prompt for LLM disambiguation."""
        recent_messages = context.items[-5:] if context.items else []
        
        history = "\n".join([
            f"{msg.role}: {msg.text_content}"
            for msg in recent_messages
            if hasattr(msg, 'text_content')
        ])
        
        prompt = f"""Analyze if the user's response is a backchannel (acknowledgment) or command (interruption).

Conversation history:
{history}

User's latest input: "{transcript}"

Is this:
A) Backchannel - User is acknowledging/listening (e.g., "yeah", "ok", "I see")
B) Command - User wants to interrupt/take turn (e.g., "wait", "stop", "let me ask")

Answer with just "backchannel" or "command"."""
        
        return prompt
    
    def _has_negation(self, text: str) -> bool:
        """Check if text contains negation."""
        return bool(self._negation_regex.search(text))
    
    def _is_question(self, text: str) -> bool:
        """Check if text is a question."""
        return bool(self._question_regex.search(text))
    
    def _is_mid_sentence(self, text: str) -> bool:
        """
        Check if user interrupted mid-sentence.
        
        Heuristics:
        - Doesn't end with punctuation
        - Contains conjunctions (and, but, because)
        """
        text_stripped = text.strip()
        
        if not text_stripped:
            return False
        
        # Check if ends with punctuation
        if text_stripped[-1] in '.!?,;':
            return False
        
        # Check for conjunctions
        conjunctions = ['and', 'but', 'because', 'so', 'if', 'when', 'while']
        text_lower = text_stripped.lower()
        
        for conj in conjunctions:
            if conj in text_lower.split():
                return True
        
        return False
    
    def _is_after_silence(self) -> bool:
        """Check if user spoke after a period of silence."""
        if self._user_last_spoke_time is None:
            return True  # First utterance
        
        silence_duration = time.time() - self._user_last_spoke_time
        return silence_duration > 2.0  # 2+ seconds of silence
    
    def _get_turns_since_user_spoke(
        self,
        chat_ctx: ChatContext | None,
    ) -> int:
        """Count how many agent turns since user's last turn."""
        if not chat_ctx or not chat_ctx.items:
            return 0
        
        turns = 0
        for item in reversed(chat_ctx.items):
            if hasattr(item, 'role'):
                if item.role == 'user':
                    break
                elif item.role == 'assistant':
                    turns += 1
        
        return turns
    
    def update_state(
        self,
        *,
        agent_started_speaking: bool | None = None,
        agent_stopped_speaking: bool | None = None,
        user_spoke: bool | None = None,
    ) -> None:
        """Update conversation state tracking."""
        if agent_started_speaking:
            self._agent_speaking_start_time = time.time()
            self._agent_turn_count += 1
        
        if agent_stopped_speaking:
            self._agent_speaking_start_time = None
            self._current_agent_utterance = ""
        
        if user_spoke:
            self._user_last_spoke_time = time.time()
    
    def reset(self) -> None:
        """Reset conversation state."""
        self._agent_speaking_start_time = None
        self._user_last_spoke_time = None
        self._agent_turn_count = 0
        self._current_agent_utterance = ""
        logger.debug("Context analyzer state reset")

