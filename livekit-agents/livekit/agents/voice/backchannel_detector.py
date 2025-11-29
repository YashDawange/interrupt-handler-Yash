"""
Advanced backchannel detection with multi-factor confidence scoring.

This module provides intelligent backchannel detection using multiple signals:
- Text analysis (word matching with variations)
- Audio features (prosody, tone, energy)
- Conversation context
- User historical patterns
- Optional ML classification
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..tokenize.basic import split_words

if TYPE_CHECKING:
    from ..llm import ChatContext

logger = logging.getLogger(__name__)


@dataclass
class BackchannelDetectionResult:
    """Result of backchannel detection analysis."""
    
    is_backchannel: bool
    """Final decision: True if detected as backchannel"""
    
    confidence_score: float
    """Overall confidence (0-1), higher = more confident it's a backchannel"""
    
    word_match_score: float
    """Score from word matching analysis (0-1)"""
    
    prosody_score: float | None = None
    """Score from audio prosody analysis (0-1)"""
    
    context_score: float | None = None
    """Score from conversation context (0-1)"""
    
    user_history_score: float | None = None
    """Score from user's historical patterns (0-1)"""
    
    ml_confidence: float | None = None
    """ML classifier confidence if available (0-1)"""
    
    processing_time_ms: float = 0.0
    """Time taken for analysis"""
    
    decision_factors: dict[str, Any] = field(default_factory=dict)
    """Additional factors that influenced the decision"""
    
    detected_language: str | None = None
    """Detected language"""


@dataclass
class UserBackchannelProfile:
    """Per-user backchannel pattern profile for adaptive learning."""
    
    user_id: str
    
    # Frequency tracking
    word_frequencies: dict[str, int] = field(default_factory=dict)
    """How often each word is used as backchannel"""
    
    total_backchannels: int = 0
    total_interruptions: int = 0
    
    # Pattern recognition
    common_patterns: list[str] = field(default_factory=list)
    """Common phrase patterns (e.g., "yeah sure", "okay fine")"""
    
    # Timing patterns
    avg_backchannel_duration: float = 0.0
    """Average duration of backchannel utterances"""
    
    # Audio patterns
    avg_pitch: float | None = None
    avg_energy: float | None = None
    
    # Adaptation
    confidence_threshold: float = 0.7
    """Personalized confidence threshold"""
    
    last_updated: float = field(default_factory=time.time)
    
    def update_from_detection(
        self,
        transcript: str,
        is_backchannel: bool,
        duration: float = 0.0,
        pitch: float | None = None,
        energy: float | None = None,
    ) -> None:
        """Update profile based on a detection event."""
        if is_backchannel:
            self.total_backchannels += 1
            words = transcript.lower().split()
            for word in words:
                self.word_frequencies[word] = self.word_frequencies.get(word, 0) + 1
            
            # Update duration average
            if duration > 0:
                if self.avg_backchannel_duration == 0:
                    self.avg_backchannel_duration = duration
                else:
                    alpha = 0.1  # Learning rate
                    self.avg_backchannel_duration = (
                        alpha * duration + (1 - alpha) * self.avg_backchannel_duration
                    )
            
            # Update audio features
            if pitch is not None:
                self.avg_pitch = pitch if self.avg_pitch is None else (
                    0.1 * pitch + 0.9 * self.avg_pitch
                )
            if energy is not None:
                self.avg_energy = energy if self.avg_energy is None else (
                    0.1 * energy + 0.9 * self.avg_energy
                )
        else:
            self.total_interruptions += 1
        
        self.last_updated = time.time()
    
    def get_word_likelihood(self, word: str) -> float:
        """Get likelihood (0-1) that this word is a backchannel for this user."""
        if self.total_backchannels == 0:
            return 0.5  # No data yet
        
        word_count = self.word_frequencies.get(word.lower(), 0)
        return min(1.0, word_count / max(1, self.total_backchannels * 0.5))
    
    def get_confidence_adjustment(self) -> float:
        """Get confidence adjustment based on user's reliability."""
        total = self.total_backchannels + self.total_interruptions
        if total < 10:
            return 0.0  # Not enough data
        
        # Users who rarely use backchannels might have different patterns
        backchannel_rate = self.total_backchannels / total
        if backchannel_rate < 0.1 or backchannel_rate > 0.9:
            return -0.1  # Be more conservative with unusual users
        return 0.1  # Boost confidence for typical users


class BackchannelDetector:
    """
    Advanced backchannel detector with multi-factor confidence scoring.
    
    This detector analyzes user input across multiple dimensions to determine
    whether it's a backchannel (passive acknowledgment) or an active interruption.
    """
    
    def __init__(
        self,
        *,
        backchannel_words: list[str] | None = None,
        confidence_threshold: float = 0.7,
        enable_prosody_analysis: bool = False,
        enable_context_analysis: bool = False,
        enable_user_learning: bool = False,
        # Scoring weights
        word_match_weight: float = 0.4,
        prosody_weight: float = 0.3,
        context_weight: float = 0.2,
        user_history_weight: float = 0.1,
    ):
        """
        Initialize the backchannel detector.
        
        Args:
            backchannel_words: List of known backchannel words
            confidence_threshold: Threshold above which to classify as backchannel
            enable_prosody_analysis: Whether to analyze audio features
            enable_context_analysis: Whether to analyze conversation context
            enable_user_learning: Whether to learn from user patterns
            word_match_weight: Weight for word matching score
            prosody_weight: Weight for prosody score
            context_weight: Weight for context score
            user_history_weight: Weight for user history score
        """
        self.backchannel_words = set(
            word.lower() for word in (backchannel_words or [])
        )
        self.confidence_threshold = confidence_threshold
        self.enable_prosody_analysis = enable_prosody_analysis
        self.enable_context_analysis = enable_context_analysis
        self.enable_user_learning = enable_user_learning
        
        # Scoring weights (should sum to 1.0)
        total_weight = word_match_weight + prosody_weight + context_weight + user_history_weight
        self.word_match_weight = word_match_weight / total_weight
        self.prosody_weight = prosody_weight / total_weight
        self.context_weight = context_weight / total_weight
        self.user_history_weight = user_history_weight / total_weight
        
        # User profiles for adaptive learning
        self.user_profiles: dict[str, UserBackchannelProfile] = {}
        
        # Expanded backchannel patterns (variations and common phrases)
        self.backchannel_patterns = self._build_backchannel_patterns()
    
    def _build_backchannel_patterns(self) -> set[str]:
        """Build expanded set of backchannel patterns including common variations."""
        patterns = set(self.backchannel_words)
        
        # Add common variations
        for word in list(self.backchannel_words):
            # Add with common suffixes
            patterns.add(f"{word}...")  # "yeah..."
            patterns.add(f"{word}.")    # "yeah."
            patterns.add(f"{word},")    # "yeah,"
            
            # Add elongated versions
            if len(word) >= 2:
                patterns.add(f"{word[0]}{word[1]}{word[1:]}")  # "yeaah"
        
        # Add common two-word combinations
        common_combos = [
            ("yeah", "sure"), ("yeah", "ok"), ("yeah", "right"),
            ("ok", "sure"), ("ok", "right"), ("right", "yeah"),
            ("got", "it"), ("i", "see"), ("makes", "sense"),
        ]
        
        for word1, word2 in common_combos:
            if word1 in self.backchannel_words or word2 in self.backchannel_words:
                patterns.add(f"{word1} {word2}")
        
        return patterns
    
    def analyze(
        self,
        transcript: str,
        *,
        agent_speaking: bool = False,
        user_id: str | None = None,
        audio_features: dict[str, float] | None = None,
        chat_context: ChatContext | None = None,
        detected_language: str | None = None,
    ) -> BackchannelDetectionResult:
        """
        Analyze transcript to determine if it's a backchannel.
        
        Args:
            transcript: The transcribed text
            agent_speaking: Whether the agent is currently speaking
            user_id: User identifier for personalization
            audio_features: Optional audio features (pitch, energy, duration, etc.)
            chat_context: Optional conversation context
            detected_language: Language detected from STT
            
        Returns:
            BackchannelDetectionResult with confidence scores
        """
        start_time = time.perf_counter()
        
        # Get or create user profile
        user_profile = None
        if self.enable_user_learning and user_id:
            user_profile = self.user_profiles.get(user_id)
            if user_profile is None:
                user_profile = UserBackchannelProfile(user_id=user_id)
                self.user_profiles[user_id] = user_profile
        
        # Component scores
        word_score = self._analyze_words(transcript, user_profile)
        prosody_score = self._analyze_prosody(audio_features, user_profile) if audio_features else None
        context_score = self._analyze_context(transcript, chat_context, agent_speaking) if chat_context else None
        history_score = self._analyze_user_history(transcript, user_profile) if user_profile else None
        
        # Calculate weighted confidence score
        confidence = self._calculate_confidence(
            word_score, prosody_score, context_score, history_score
        )
        
        # Apply user-specific adjustments
        if user_profile:
            confidence += user_profile.get_confidence_adjustment()
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        
        # Make decision
        is_backchannel = confidence >= self.confidence_threshold
        
        # Prepare result
        processing_time = (time.perf_counter() - start_time) * 1000  # ms
        
        result = BackchannelDetectionResult(
            is_backchannel=is_backchannel,
            confidence_score=confidence,
            word_match_score=word_score,
            prosody_score=prosody_score,
            context_score=context_score,
            user_history_score=history_score,
            processing_time_ms=processing_time,
            detected_language=detected_language,
            decision_factors={
                "agent_speaking": agent_speaking,
                "transcript_length": len(transcript),
                "word_count": len(split_words(transcript)),
                "has_user_profile": user_profile is not None,
            },
        )
        
        # Update user profile if learning enabled
        if user_profile and self.enable_user_learning:
            duration = audio_features.get("duration", 0.0) if audio_features else 0.0
            pitch = audio_features.get("pitch", None) if audio_features else None
            energy = audio_features.get("energy", None) if audio_features else None
            user_profile.update_from_detection(
                transcript, is_backchannel, duration, pitch, energy
            )
        
        return result
    
    def _analyze_words(
        self, transcript: str, user_profile: UserBackchannelProfile | None
    ) -> float:
        """
        Analyze transcript words for backchannel indicators.
        
        Returns score 0-1, where 1 = very likely backchannel
        """
        if not transcript:
            return 0.0
        
        text = transcript.strip().lower()
        
        # Check for exact phrase match
        if text in self.backchannel_patterns:
            return 1.0
        
        # Analyze individual words
        words = split_words(text, split_character=True)
        if not words:
            return 0.0
        
        # Count backchannel words vs total words
        backchannel_count = 0
        total_score = 0.0
        
        for word in words:
            word_clean = word.lower().strip(".,!?;:")
            
            # Check if word is in backchannel list
            if word_clean in self.backchannel_words:
                backchannel_count += 1
                total_score += 1.0
            elif user_profile:
                # Check user's personalized likelihood
                likelihood = user_profile.get_word_likelihood(word_clean)
                if likelihood > 0.5:
                    backchannel_count += likelihood
                    total_score += likelihood
        
        # Calculate score
        if len(words) == 0:
            return 0.0
        
        # If ALL words are backchannels, high confidence
        if backchannel_count >= len(words):
            return 0.95
        
        # If MOST words are backchannels, medium-high confidence
        ratio = backchannel_count / len(words)
        if ratio > 0.7:
            return 0.7 + (ratio - 0.7) * 0.8  # 0.7 to 0.94
        
        # If SOME words are backchannels, depends on count
        if backchannel_count > 0:
            # Penalize longer utterances with backchannel words mixed in
            length_penalty = max(0.5, 1.0 - (len(words) - backchannel_count) * 0.1)
            return ratio * length_penalty
        
        # No backchannel words found
        return 0.0
    
    def _analyze_prosody(
        self,
        audio_features: dict[str, float] | None,
        user_profile: UserBackchannelProfile | None,
    ) -> float | None:
        """
        Analyze audio prosody features.
        
        Returns score 0-1, where 1 = prosody strongly indicates backchannel
        """
        if not self.enable_prosody_analysis or not audio_features:
            return None
        
        score = 0.5  # Neutral baseline
        
        # Short duration suggests backchannel
        duration = audio_features.get("duration", 0.0)
        if duration > 0:
            if duration < 0.5:  # Very short
                score += 0.2
            elif duration < 1.0:  # Short
                score += 0.1
            elif duration > 2.0:  # Long utterances less likely backchannel
                score -= 0.2
        
        # Flat/falling pitch contour suggests backchannel
        pitch_contour = audio_features.get("pitch_contour", "flat")
        if pitch_contour == "falling":
            score += 0.15
        elif pitch_contour == "flat":
            score += 0.1
        elif pitch_contour == "rising":  # Question-like
            score -= 0.2
        
        # Lower energy suggests casual backchannel
        energy = audio_features.get("energy", 0.5)
        if energy < 0.3:
            score += 0.1
        elif energy > 0.7:  # High energy suggests engagement/interruption
            score -= 0.15
        
        # Compare to user's typical patterns
        if user_profile and user_profile.avg_pitch is not None:
            pitch = audio_features.get("pitch", 0.0)
            if pitch > 0:
                pitch_diff = abs(pitch - user_profile.avg_pitch) / user_profile.avg_pitch
                if pitch_diff < 0.1:  # Similar to typical backchannel pitch
                    score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _analyze_context(
        self,
        transcript: str,
        chat_context: ChatContext | None,
        agent_speaking: bool,
    ) -> float | None:
        """
        Analyze conversation context.
        
        Returns score 0-1, where 1 = context strongly suggests backchannel
        """
        if not self.enable_context_analysis or not chat_context:
            return None
        
        score = 0.5  # Neutral baseline
        
        # If agent was speaking, more likely backchannel
        if agent_speaking:
            score += 0.2
        
        # Check last agent message
        recent_items = chat_context.items[-5:] if chat_context.items else []
        agent_messages = [
            item for item in recent_items
            if hasattr(item, 'role') and item.role == "assistant"
        ]
        
        if agent_messages:
            last_agent_msg = agent_messages[-1]
            agent_text = ""
            if hasattr(last_agent_msg, 'content'):
                if isinstance(last_agent_msg.content, list):
                    agent_text = " ".join(
                        str(c) for c in last_agent_msg.content if isinstance(c, str)
                    )
                else:
                    agent_text = str(last_agent_msg.content)
            
            # If agent was explaining something (long message), backchannels more likely
            if len(agent_text) > 200:
                score += 0.15
            
            # If agent asked a yes/no question, short affirmative more likely backchannel
            agent_lower = agent_text.lower()
            if any(q in agent_lower for q in ["are you", "do you", "can you", "will you"]):
                if transcript.lower() in ["yes", "yeah", "yep", "sure", "ok", "okay"]:
                    score -= 0.2  # Actually an answer, not a backchannel
        
        # Check for negation in transcript (reduces backchannel likelihood)
        negations = ["no", "not", "don't", "stop", "wait"]
        if any(neg in transcript.lower() for neg in negations):
            score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def _analyze_user_history(
        self, transcript: str, user_profile: UserBackchannelProfile | None
    ) -> float | None:
        """
        Analyze user's historical patterns.
        
        Returns score 0-1 based on how typical this is for the user
        """
        if not user_profile or user_profile.total_backchannels == 0:
            return None
        
        words = transcript.lower().split()
        if not words:
            return 0.5
        
        # Calculate average likelihood across all words
        likelihoods = [user_profile.get_word_likelihood(word) for word in words]
        avg_likelihood = sum(likelihoods) / len(likelihoods)
        
        return avg_likelihood
    
    def _calculate_confidence(
        self,
        word_score: float,
        prosody_score: float | None,
        context_score: float | None,
        history_score: float | None,
    ) -> float:
        """Calculate weighted confidence score from component scores."""
        total_weight = 0.0
        weighted_sum = 0.0
        
        # Word matching (always available)
        weighted_sum += word_score * self.word_match_weight
        total_weight += self.word_match_weight
        
        # Prosody (if available)
        if prosody_score is not None:
            weighted_sum += prosody_score * self.prosody_weight
            total_weight += self.prosody_weight
        
        # Context (if available)
        if context_score is not None:
            weighted_sum += context_score * self.context_weight
            total_weight += self.context_weight
        
        # User history (if available)
        if history_score is not None:
            weighted_sum += history_score * self.user_history_weight
            total_weight += self.user_history_weight
        
        # Normalize by actual total weight used
        if total_weight == 0:
            return 0.5
        
        return weighted_sum / total_weight
    
    def update_configuration(
        self,
        *,
        backchannel_words: list[str] | None = None,
        confidence_threshold: float | None = None,
        enable_prosody_analysis: bool | None = None,
        enable_context_analysis: bool | None = None,
        enable_user_learning: bool | None = None,
    ) -> None:
        """Dynamically update detector configuration."""
        if backchannel_words is not None:
            self.backchannel_words = set(word.lower() for word in backchannel_words)
            self.backchannel_patterns = self._build_backchannel_patterns()
        
        if confidence_threshold is not None:
            self.confidence_threshold = confidence_threshold
        
        if enable_prosody_analysis is not None:
            self.enable_prosody_analysis = enable_prosody_analysis
        
        if enable_context_analysis is not None:
            self.enable_context_analysis = enable_context_analysis
        
        if enable_user_learning is not None:
            self.enable_user_learning = enable_user_learning

