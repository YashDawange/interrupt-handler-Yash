"""
Confidence Scoring System for Backchannel Detection

Implements multi-factor confidence scoring that combines:
- Text/word matching analysis
- Audio prosody features
- Conversation context
- User history patterns
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...log import logger
from ...tokenize.basic import split_words

if TYPE_CHECKING:
    from ..agent_session import AgentSession


@dataclass
class BackchannelConfidence:
    """
    Represents the confidence that a user utterance is a backchannel.
    
    Attributes:
        overall_score: Final confidence (0-1, higher = more likely backchannel)
        word_match_score: Score from text/word analysis (0-1)
        prosody_score: Score from audio features (0-1, None if unavailable)
        context_score: Score from conversation context (0-1)
        user_history_score: Score from learned user patterns (0-1, None if unavailable)
        decision: Final decision (True = backchannel, False = command)
        threshold: Threshold used for decision
        transcript: The analyzed text
        features: Additional features used in scoring
        timestamp: When this confidence was computed
    """
    
    overall_score: float
    word_match_score: float
    prosody_score: float | None
    context_score: float
    user_history_score: float | None
    decision: bool
    threshold: float
    transcript: str
    features: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    @property
    def is_backchannel(self) -> bool:
        """Returns True if classified as backchannel."""
        return self.decision
    
    @property
    def confidence_level(self) -> str:
        """Returns confidence level as string."""
        if self.overall_score >= 0.8:
            return "very_high"
        elif self.overall_score >= 0.6:
            return "high"
        elif self.overall_score >= 0.4:
            return "medium"
        elif self.overall_score >= 0.2:
            return "low"
        else:
            return "very_low"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/metrics."""
        return {
            "overall_score": round(self.overall_score, 3),
            "word_match_score": round(self.word_match_score, 3),
            "prosody_score": round(self.prosody_score, 3) if self.prosody_score is not None else None,
            "context_score": round(self.context_score, 3),
            "user_history_score": round(self.user_history_score, 3) if self.user_history_score is not None else None,
            "decision": self.decision,
            "confidence_level": self.confidence_level,
            "transcript": self.transcript,
            "features": self.features,
        }


class ConfidenceScorer:
    """
    Multi-factor confidence scorer for backchannel detection.
    
    Combines multiple signals to determine if user input is backchannel:
    - Word matching (0.4 weight)
    - Audio prosody (0.3 weight)
    - Context analysis (0.2 weight)
    - User history (0.1 weight)
    """
    
    # Weights for each scoring component
    WEIGHT_WORD_MATCH = 0.4
    WEIGHT_PROSODY = 0.3
    WEIGHT_CONTEXT = 0.2
    WEIGHT_USER_HISTORY = 0.1
    
    # Default thresholds
    DEFAULT_THRESHOLD = 0.5  # 50% confidence = backchannel
    STRICT_THRESHOLD = 0.7   # 70% confidence = backchannel
    PERMISSIVE_THRESHOLD = 0.3  # 30% confidence = backchannel
    
    def __init__(
        self,
        *,
        backchannel_words: list[str] | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        enable_prosody: bool = True,
        enable_context: bool = True,
        enable_user_history: bool = True,
    ):
        """
        Initialize confidence scorer.
        
        Args:
            backchannel_words: List of words considered backchannels
            threshold: Confidence threshold for backchannel decision (0-1)
            enable_prosody: Whether to use audio prosody analysis
            enable_context: Whether to use conversation context
            enable_user_history: Whether to use user history patterns
        """
        self._backchannel_words = set(
            word.lower() for word in (backchannel_words or [])
        )
        self._threshold = max(0.0, min(1.0, threshold))
        self._enable_prosody = enable_prosody
        self._enable_context = enable_context
        self._enable_user_history = enable_user_history
        
        # Track statistics for adaptive learning
        self._stats = {
            "total_analyzed": 0,
            "backchannels_detected": 0,
            "commands_detected": 0,
            "avg_backchannel_score": 0.0,
            "avg_command_score": 0.0,
        }
    
    def compute_confidence(
        self,
        transcript: str,
        *,
        prosody_features: dict[str, float] | None = None,
        context_data: dict | None = None,
        user_profile: dict | None = None,
        agent_speaking: bool = True,
    ) -> BackchannelConfidence:
        """
        Compute overall confidence that transcript is a backchannel.
        
        Args:
            transcript: The transcribed text to analyze
            prosody_features: Audio features (pitch, energy, duration, etc.)
            context_data: Conversation context (recent messages, topic, etc.)
            user_profile: User's historical backchannel patterns
            agent_speaking: Whether agent is currently speaking
            
        Returns:
            BackchannelConfidence object with scores and decision
        """
        # Compute individual scores
        word_score = self._compute_word_match_score(transcript)
        prosody_score = (
            self._compute_prosody_score(prosody_features)
            if self._enable_prosody and prosody_features
            else None
        )
        context_score = (
            self._compute_context_score(transcript, context_data, agent_speaking)
            if self._enable_context
            else 0.5  # Neutral if disabled
        )
        user_score = (
            self._compute_user_history_score(transcript, user_profile)
            if self._enable_user_history and user_profile
            else None
        )
        
        # Compute weighted overall score
        overall = self._compute_overall_score(
            word_score, prosody_score, context_score, user_score
        )
        
        # Make decision
        decision = overall >= self._threshold
        
        # Track statistics
        self._update_stats(overall, decision)
        
        # Build confidence object
        confidence = BackchannelConfidence(
            overall_score=overall,
            word_match_score=word_score,
            prosody_score=prosody_score,
            context_score=context_score,
            user_history_score=user_score,
            decision=decision,
            threshold=self._threshold,
            transcript=transcript,
            features={
                "agent_speaking": agent_speaking,
                "word_count": len(split_words(transcript, split_character=True)),
                "prosody_available": prosody_features is not None,
                "user_profile_available": user_profile is not None,
            },
        )
        
        logger.debug(
            f"Backchannel confidence: {overall:.3f} (threshold={self._threshold:.3f}) "
            f"[word={word_score:.2f}, prosody={prosody_score:.2f if prosody_score else 'N/A'}, "
            f"context={context_score:.2f}, user={user_score:.2f if user_score else 'N/A'}] "
            f"→ {'BACKCHANNEL' if decision else 'COMMAND'}: '{transcript}'"
        )
        
        return confidence
    
    def _compute_word_match_score(self, transcript: str) -> float:
        """
        Compute score based on word matching.
        
        Returns 1.0 if all words are backchannels, 0.0 if none are.
        Handles partial matches proportionally.
        """
        if not transcript or not self._backchannel_words:
            return 0.0
        
        text = transcript.strip().lower()
        words = split_words(text, split_character=True)
        
        if not words:
            return 0.0
        
        # Count backchannel words
        backchannel_count = sum(
            1 for word in words
            if word.lower() in self._backchannel_words
        )
        
        # Exact match (all words are backchannels) = 1.0
        # Partial match = proportional score
        score = backchannel_count / len(words)
        
        # Boost score if it's a short utterance (1-2 words)
        if len(words) <= 2 and backchannel_count > 0:
            score = min(1.0, score * 1.2)
        
        return score
    
    def _compute_prosody_score(
        self, prosody_features: dict[str, float] | None
    ) -> float:
        """
        Compute score based on audio prosody features.
        
        Backchannel characteristics:
        - Flat or falling pitch (not rising like questions)
        - Short duration
        - Medium-low energy
        - Quick tempo
        """
        if not prosody_features:
            return 0.5  # Neutral if not available
        
        score = 0.5  # Start neutral
        
        # Pitch contour: flat/falling = backchannel, rising = question/command
        if "pitch_contour" in prosody_features:
            contour = prosody_features["pitch_contour"]
            if contour < -0.1:  # Falling
                score += 0.15
            elif contour > 0.1:  # Rising (question)
                score -= 0.15
        
        # Duration: short = backchannel
        if "duration" in prosody_features:
            duration = prosody_features["duration"]
            if duration < 0.5:  # Less than 500ms
                score += 0.15
            elif duration > 1.5:  # More than 1.5s
                score -= 0.10
        
        # Energy: medium-low = backchannel
        if "energy" in prosody_features:
            energy = prosody_features["energy"]
            if 0.3 <= energy <= 0.7:  # Medium range
                score += 0.10
            elif energy > 0.8:  # High energy (command)
                score -= 0.10
        
        # Tempo: quick = backchannel
        if "tempo" in prosody_features:
            tempo = prosody_features["tempo"]
            if tempo > 1.2:  # Fast
                score += 0.10
        
        return max(0.0, min(1.0, score))
    
    def _compute_context_score(
        self,
        transcript: str,
        context_data: dict | None,
        agent_speaking: bool,
    ) -> float:
        """
        Compute score based on conversation context.
        
        Considers:
        - Agent's recent utterances (long explanation = more likely backchannel)
        - Conversation topic
        - Position in dialogue flow
        """
        score = 0.5  # Start neutral
        
        if not context_data:
            # If agent is speaking, slightly favor backchannel
            return 0.6 if agent_speaking else 0.4
        
        # Long agent utterance = more likely user is backchanneling
        if "agent_utterance_duration" in context_data:
            duration = context_data["agent_utterance_duration"]
            if duration > 5.0:  # Agent speaking for >5s
                score += 0.15
            elif duration > 10.0:  # Agent speaking for >10s
                score += 0.25
        
        # Check for negation patterns ("don't stop" shouldn't interrupt)
        if "has_negation" in context_data and context_data["has_negation"]:
            score += 0.10
        
        # Question from agent = more likely user answers (not backchannel)
        if "agent_asked_question" in context_data and context_data["agent_asked_question"]:
            score -= 0.15
        
        # Standalone utterance (after silence) more likely to be command
        if "after_silence" in context_data and context_data["after_silence"]:
            score -= 0.10
        
        return max(0.0, min(1.0, score))
    
    def _compute_user_history_score(
        self,
        transcript: str,
        user_profile: dict | None,
    ) -> float:
        """
        Compute score based on user's historical patterns.
        
        Learns user-specific backchannel words and patterns.
        """
        if not user_profile:
            return 0.5  # Neutral if no history
        
        # Check if this exact phrase has been seen before
        backchannel_freq = user_profile.get("backchannel_phrases", {})
        command_freq = user_profile.get("command_phrases", {})
        
        text_lower = transcript.lower().strip()
        
        # If we've seen this exact phrase before
        backchannel_count = backchannel_freq.get(text_lower, 0)
        command_count = command_freq.get(text_lower, 0)
        total_count = backchannel_count + command_count
        
        if total_count > 0:
            # Use historical ratio
            return backchannel_count / total_count
        
        # Otherwise use overall user tendency
        total_backchannels = user_profile.get("total_backchannels", 0)
        total_commands = user_profile.get("total_commands", 0)
        total = total_backchannels + total_commands
        
        if total > 10:  # Need sufficient history
            return total_backchannels / total
        
        return 0.5  # Neutral if insufficient history
    
    def _compute_overall_score(
        self,
        word_score: float,
        prosody_score: float | None,
        context_score: float,
        user_score: float | None,
    ) -> float:
        """
        Compute weighted overall confidence score.
        
        Automatically adjusts weights if some signals are unavailable.
        """
        scores = [(word_score, self.WEIGHT_WORD_MATCH)]
        total_weight = self.WEIGHT_WORD_MATCH
        
        if prosody_score is not None:
            scores.append((prosody_score, self.WEIGHT_PROSODY))
            total_weight += self.WEIGHT_PROSODY
        
        scores.append((context_score, self.WEIGHT_CONTEXT))
        total_weight += self.WEIGHT_CONTEXT
        
        if user_score is not None:
            scores.append((user_score, self.WEIGHT_USER_HISTORY))
            total_weight += self.WEIGHT_USER_HISTORY
        
        # Normalize weights to sum to 1.0
        normalized_scores = [
            (score, weight / total_weight)
            for score, weight in scores
        ]
        
        # Compute weighted average
        overall = sum(score * weight for score, weight in normalized_scores)
        
        return max(0.0, min(1.0, overall))
    
    def _update_stats(self, score: float, is_backchannel: bool) -> None:
        """Update internal statistics for monitoring."""
        self._stats["total_analyzed"] += 1
        
        if is_backchannel:
            self._stats["backchannels_detected"] += 1
            # Running average of backchannel scores
            prev_avg = self._stats["avg_backchannel_score"]
            count = self._stats["backchannels_detected"]
            self._stats["avg_backchannel_score"] = (
                (prev_avg * (count - 1) + score) / count
            )
        else:
            self._stats["commands_detected"] += 1
            # Running average of command scores
            prev_avg = self._stats["avg_command_score"]
            count = self._stats["commands_detected"]
            self._stats["avg_command_score"] = (
                (prev_avg * (count - 1) + score) / count
            )
    
    def get_stats(self) -> dict:
        """Get scorer statistics."""
        return self._stats.copy()
    
    def update_threshold(self, threshold: float) -> None:
        """Update decision threshold (0-1)."""
        self._threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Updated backchannel threshold to {self._threshold:.2f}")
    
    def update_backchannel_words(self, words: list[str]) -> None:
        """Update backchannel word list."""
        self._backchannel_words = set(word.lower() for word in words)
        logger.info(f"Updated backchannel words: {len(self._backchannel_words)} words")

