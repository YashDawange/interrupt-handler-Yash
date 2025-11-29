"""
User Profile System for Adaptive Backchannel Learning

Learns each user's specific backchannel patterns over time:
- Tracks user-specific words and phrases
- Adapts confidence thresholds
- Improves accuracy through interaction
- Supports cross-session persistence
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ....log import logger

if TYPE_CHECKING:
    from .confidence import BackchannelConfidence


@dataclass
class UserBackchannelProfile:
    """
    User-specific backchannel pattern profile.
    
    Learns and adapts to individual user's communication style.
    """
    
    user_id: str
    
    # Phrase frequency tracking
    backchannel_phrases: dict[str, int] = field(default_factory=dict)
    command_phrases: dict[str, int] = field(default_factory=dict)
    
    # Overall statistics
    total_backchannels: int = 0
    total_commands: int = 0
    total_interactions: int = 0
    
    # Confidence threshold adaptation
    optimal_threshold: float | None = None
    threshold_history: list[tuple[float, float]] = field(default_factory=list)  # (threshold, accuracy)
    
    # Timing patterns
    avg_backchannel_duration: float = 0.5  # seconds
    avg_command_duration: float = 1.0  # seconds
    
    # Audio characteristics (learned baselines)
    user_pitch_baseline: float | None = None
    user_energy_baseline: float | None = None
    user_tempo_baseline: float | None = None
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    session_count: int = 0
    
    def record_interaction(
        self,
        text: str,
        is_backchannel: bool,
        confidence: BackchannelConfidence | None = None,
    ) -> None:
        """
        Record a user interaction for learning.
        
        Args:
            text: The transcribed text
            is_backchannel: Whether it was classified as backchannel
            confidence: Full confidence object if available
        """
        self.total_interactions += 1
        self.last_updated = time.time()
        
        text_lower = text.lower().strip()
        
        if is_backchannel:
            self.total_backchannels += 1
            self.backchannel_phrases[text_lower] = (
                self.backchannel_phrases.get(text_lower, 0) + 1
            )
            
            # Update duration if available
            if confidence and confidence.features.get("duration"):
                duration = confidence.features["duration"]
                self._update_running_average(
                    "avg_backchannel_duration",
                    duration,
                    self.total_backchannels,
                )
        else:
            self.total_commands += 1
            self.command_phrases[text_lower] = (
                self.command_phrases.get(text_lower, 0) + 1
            )
            
            # Update duration if available
            if confidence and confidence.features.get("duration"):
                duration = confidence.features["duration"]
                self._update_running_average(
                    "avg_command_duration",
                    duration,
                    self.total_commands,
                )
        
        # Update audio baselines if available
        if confidence:
            self._update_audio_baselines(confidence, is_backchannel)
    
    def _update_running_average(
        self,
        attr_name: str,
        new_value: float,
        count: int,
    ) -> None:
        """Update a running average attribute."""
        current = getattr(self, attr_name)
        updated = (current * (count - 1) + new_value) / count
        setattr(self, attr_name, updated)
    
    def _update_audio_baselines(
        self,
        confidence: BackchannelConfidence,
        is_backchannel: bool,
    ) -> None:
        """Update user's audio characteristic baselines."""
        # Only learn from backchannels (consistent, natural utterances)
        if not is_backchannel:
            return
        
        # Extract audio features from confidence
        prosody = confidence.features.get("prosody", {})
        
        if "pitch_mean" in prosody:
            pitch = prosody["pitch_mean"]
            if self.user_pitch_baseline is None:
                self.user_pitch_baseline = pitch
            else:
                # Running average
                self.user_pitch_baseline = (
                    self.user_pitch_baseline * 0.9 + pitch * 0.1
                )
        
        if "energy_mean" in prosody:
            energy = prosody["energy_mean"]
            if self.user_energy_baseline is None:
                self.user_energy_baseline = energy
            else:
                self.user_energy_baseline = (
                    self.user_energy_baseline * 0.9 + energy * 0.1
                )
        
        if "tempo" in prosody:
            tempo = prosody["tempo"]
            if self.user_tempo_baseline is None:
                self.user_tempo_baseline = tempo
            else:
                self.user_tempo_baseline = (
                    self.user_tempo_baseline * 0.9 + tempo * 0.1
                )
    
    def get_phrase_confidence(self, text: str) -> float:
        """
        Get confidence that text is a backchannel based on user history.
        
        Returns:
            Confidence score 0-1 (0.5 if unknown)
        """
        text_lower = text.lower().strip()
        
        backchannel_count = self.backchannel_phrases.get(text_lower, 0)
        command_count = self.command_phrases.get(text_lower, 0)
        total = backchannel_count + command_count
        
        if total == 0:
            return 0.5  # Unknown
        
        return backchannel_count / total
    
    def get_top_backchannels(self, n: int = 10) -> list[tuple[str, int]]:
        """Get top N most frequent backchannel phrases."""
        return sorted(
            self.backchannel_phrases.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:n]
    
    def get_top_commands(self, n: int = 10) -> list[tuple[str, int]]:
        """Get top N most frequent command phrases."""
        return sorted(
            self.command_phrases.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:n]
    
    def adapt_threshold(
        self,
        current_threshold: float,
        accuracy: float,
    ) -> float:
        """
        Adapt confidence threshold based on accuracy.
        
        Args:
            current_threshold: Current threshold being used
            accuracy: Measured accuracy (0-1)
            
        Returns:
            Suggested new threshold
        """
        # Record this threshold's performance
        self.threshold_history.append((current_threshold, accuracy))
        
        # Keep only recent history (last 20 measurements)
        if len(self.threshold_history) > 20:
            self.threshold_history = self.threshold_history[-20:]
        
        # If accuracy is good (>85%), keep current threshold
        if accuracy >= 0.85:
            self.optimal_threshold = current_threshold
            return current_threshold
        
        # If accuracy is low, adjust threshold
        if accuracy < 0.70:
            # Find best threshold from history
            if len(self.threshold_history) >= 5:
                best_threshold, best_accuracy = max(
                    self.threshold_history,
                    key=lambda x: x[1],
                )
                
                if best_accuracy > accuracy:
                    logger.info(
                        f"Adapting threshold: {current_threshold:.2f} → {best_threshold:.2f} "
                        f"(accuracy: {accuracy:.1%} → {best_accuracy:.1%})"
                    )
                    self.optimal_threshold = best_threshold
                    return best_threshold
        
        return current_threshold
    
    def get_summary(self) -> dict:
        """Get profile summary for display."""
        total = self.total_backchannels + self.total_commands
        backchannel_rate = (
            self.total_backchannels / total if total > 0 else 0
        )
        
        return {
            "user_id": self.user_id,
            "total_interactions": self.total_interactions,
            "total_backchannels": self.total_backchannels,
            "total_commands": self.total_commands,
            "backchannel_rate": round(backchannel_rate, 3),
            "unique_backchannel_phrases": len(self.backchannel_phrases),
            "unique_command_phrases": len(self.command_phrases),
            "optimal_threshold": self.optimal_threshold,
            "session_count": self.session_count,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "top_backchannels": dict(self.get_top_backchannels(5)),
            "top_commands": dict(self.get_top_commands(5)),
            "audio_baselines": {
                "pitch": self.user_pitch_baseline,
                "energy": self.user_energy_baseline,
                "tempo": self.user_tempo_baseline,
            },
        }
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "user_id": self.user_id,
            "backchannel_phrases": self.backchannel_phrases,
            "command_phrases": self.command_phrases,
            "total_backchannels": self.total_backchannels,
            "total_commands": self.total_commands,
            "total_interactions": self.total_interactions,
            "optimal_threshold": self.optimal_threshold,
            "threshold_history": self.threshold_history,
            "avg_backchannel_duration": self.avg_backchannel_duration,
            "avg_command_duration": self.avg_command_duration,
            "user_pitch_baseline": self.user_pitch_baseline,
            "user_energy_baseline": self.user_energy_baseline,
            "user_tempo_baseline": self.user_tempo_baseline,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "session_count": self.session_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> UserBackchannelProfile:
        """Deserialize from dictionary."""
        return cls(**data)
    
    def save(self, filepath: str | Path) -> None:
        """Save profile to file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.info(f"Saved user profile to {filepath}")
    
    @classmethod
    def load(cls, filepath: str | Path) -> UserBackchannelProfile:
        """Load profile from file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        
        profile = cls.from_dict(data)
        logger.info(f"Loaded user profile from {filepath}")
        return profile


class UserProfileManager:
    """
    Manages user profiles with automatic persistence.
    
    Handles:
    - Loading/saving profiles
    - Profile caching
    - Automatic persistence
    """
    
    def __init__(
        self,
        *,
        profiles_dir: str | Path = ".user_profiles",
        auto_save: bool = True,
        save_interval: int = 10,  # Save every N interactions
    ):
        """
        Initialize profile manager.
        
        Args:
            profiles_dir: Directory to store profiles
            auto_save: Whether to auto-save profiles
            save_interval: Save after this many interactions
        """
        self._profiles_dir = Path(profiles_dir)
        self._auto_save = auto_save
        self._save_interval = save_interval
        
        # In-memory profile cache
        self._profiles: dict[str, UserBackchannelProfile] = {}
        
        # Track interactions since last save
        self._interactions_since_save: dict[str, int] = {}
        
        logger.info(f"UserProfileManager initialized: profiles_dir={self._profiles_dir}")
    
    def get_profile(self, user_id: str) -> UserBackchannelProfile:
        """
        Get or create user profile.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            UserBackchannelProfile for this user
        """
        # Check cache
        if user_id in self._profiles:
            return self._profiles[user_id]
        
        # Try to load from disk
        filepath = self._profiles_dir / f"{user_id}.json"
        
        if filepath.exists():
            try:
                profile = UserBackchannelProfile.load(filepath)
                profile.session_count += 1
                self._profiles[user_id] = profile
                logger.info(f"Loaded existing profile for user {user_id}")
                return profile
            except Exception as e:
                logger.warning(f"Failed to load profile for {user_id}: {e}")
        
        # Create new profile
        profile = UserBackchannelProfile(user_id=user_id)
        self._profiles[user_id] = profile
        self._interactions_since_save[user_id] = 0
        logger.info(f"Created new profile for user {user_id}")
        
        return profile
    
    def record_interaction(
        self,
        user_id: str,
        text: str,
        is_backchannel: bool,
        confidence: BackchannelConfidence | None = None,
    ) -> None:
        """Record user interaction in profile."""
        profile = self.get_profile(user_id)
        profile.record_interaction(text, is_backchannel, confidence)
        
        # Track for auto-save
        self._interactions_since_save[user_id] = (
            self._interactions_since_save.get(user_id, 0) + 1
        )
        
        # Auto-save if threshold reached
        if (
            self._auto_save
            and self._interactions_since_save[user_id] >= self._save_interval
        ):
            self.save_profile(user_id)
            self._interactions_since_save[user_id] = 0
    
    def save_profile(self, user_id: str) -> None:
        """Save user profile to disk."""
        if user_id not in self._profiles:
            return
        
        profile = self._profiles[user_id]
        filepath = self._profiles_dir / f"{user_id}.json"
        
        try:
            profile.save(filepath)
        except Exception as e:
            logger.error(f"Failed to save profile for {user_id}: {e}")
    
    def save_all_profiles(self) -> None:
        """Save all profiles to disk."""
        for user_id in self._profiles:
            self.save_profile(user_id)
        
        logger.info(f"Saved {len(self._profiles)} user profiles")
    
    def get_all_profiles(self) -> dict[str, UserBackchannelProfile]:
        """Get all loaded profiles."""
        return self._profiles.copy()
    
    def clear_cache(self) -> None:
        """Clear in-memory profile cache."""
        self._profiles.clear()
        self._interactions_since_save.clear()
        logger.info("Cleared profile cache")

