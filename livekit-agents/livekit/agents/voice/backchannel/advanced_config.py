"""
Advanced Backchannel Configuration System

Provides real-time configuration updates and A/B testing support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .language_support import Language

if TYPE_CHECKING:
    from .confidence import ConfidenceScorer

logger = logging.getLogger(__name__)


@dataclass
class AdvancedBackchannelConfig:
    """
    Advanced configuration for backchannel detection.
    
    All parameters can be updated in real-time.
    """
    
    # Core settings
    enabled: bool = True
    threshold: float = 0.5  # Confidence threshold (0-1)
    sensitivity: float = 0.5  # Overall sensitivity (0=strict, 1=permissive)
    
    # Feature toggles
    enable_ml_classifier: bool = False
    enable_prosody_analysis: bool = True
    enable_context_analysis: bool = True
    enable_user_learning: bool = True
    
    # Word lists
    backchannel_words: list[str] = field(default_factory=list)
    command_words: list[str] = field(default_factory=list)
    
    # Language settings
    language: Language | None = None
    auto_detect_language: bool = True
    multi_language_mode: bool = False
    
    # Performance tuning
    max_processing_time_ms: float = 15.0
    enable_caching: bool = True
    
    # Debugging
    verbose_logging: bool = False
    emit_decision_events: bool = True
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "threshold": self.threshold,
            "sensitivity": self.sensitivity,
            "enable_ml_classifier": self.enable_ml_classifier,
            "enable_prosody_analysis": self.enable_prosody_analysis,
            "enable_context_analysis": self.enable_context_analysis,
            "enable_user_learning": self.enable_user_learning,
            "backchannel_words_count": len(self.backchannel_words),
            "language": self.language.value if self.language else None,
            "auto_detect_language": self.auto_detect_language,
            "multi_language_mode": self.multi_language_mode,
            "verbose_logging": self.verbose_logging,
        }


class DynamicConfigManager:
    """
    Manages dynamic configuration updates.
    
    Allows real-time configuration changes without restarting the agent.
    """
    
    def __init__(self, config: AdvancedBackchannelConfig | None = None):
        """
        Initialize config manager.
        
        Args:
            config: Initial configuration
        """
        self._config = config or AdvancedBackchannelConfig()
        self._config_history: list[tuple[float, AdvancedBackchannelConfig]] = []
        
        logger.info("DynamicConfigManager initialized")
    
    @property
    def config(self) -> AdvancedBackchannelConfig:
        """Get current configuration."""
        return self._config
    
    def update_config(
        self,
        *,
        enabled: bool | None = None,
        threshold: float | None = None,
        sensitivity: float | None = None,
        enable_ml_classifier: bool | None = None,
        enable_prosody_analysis: bool | None = None,
        enable_context_analysis: bool | None = None,
        enable_user_learning: bool | None = None,
        backchannel_words: list[str] | None = None,
        language: Language | None = None,
        auto_detect_language: bool | None = None,
        verbose_logging: bool | None = None,
    ) -> AdvancedBackchannelConfig:
        """
        Update configuration in real-time.
        
        Only provided parameters will be updated.
        
        Returns:
            Updated configuration
        """
        import time
        
        # Store old config in history
        self._config_history.append((time.time(), self._config))
        
        # Keep only recent history (last 20 changes)
        if len(self._config_history) > 20:
            self._config_history = self._config_history[-20:]
        
        # Update config
        if enabled is not None:
            self._config.enabled = enabled
        if threshold is not None:
            self._config.threshold = max(0.0, min(1.0, threshold))
        if sensitivity is not None:
            self._config.sensitivity = max(0.0, min(1.0, sensitivity))
        if enable_ml_classifier is not None:
            self._config.enable_ml_classifier = enable_ml_classifier
        if enable_prosody_analysis is not None:
            self._config.enable_prosody_analysis = enable_prosody_analysis
        if enable_context_analysis is not None:
            self._config.enable_context_analysis = enable_context_analysis
        if enable_user_learning is not None:
            self._config.enable_user_learning = enable_user_learning
        if backchannel_words is not None:
            self._config.backchannel_words = backchannel_words
        if language is not None:
            self._config.language = language
        if auto_detect_language is not None:
            self._config.auto_detect_language = auto_detect_language
        if verbose_logging is not None:
            self._config.verbose_logging = verbose_logging
        
        logger.info(f"Configuration updated: {self._get_update_summary()}")
        
        return self._config
    
    def _get_update_summary(self) -> str:
        """Get summary of what was updated."""
        if not self._config_history:
            return "initial"
        
        old_config = self._config_history[-1][1]
        changes = []
        
        if old_config.enabled != self._config.enabled:
            changes.append(f"enabled={self._config.enabled}")
        if old_config.threshold != self._config.threshold:
            changes.append(f"threshold={self._config.threshold:.2f}")
        if old_config.enable_ml_classifier != self._config.enable_ml_classifier:
            changes.append(f"ml={self._config.enable_ml_classifier}")
        
        return ", ".join(changes) if changes else "no changes"
    
    def reset_to_default(self) -> AdvancedBackchannelConfig:
        """Reset to default configuration."""
        self._config = AdvancedBackchannelConfig()
        logger.info("Configuration reset to default")
        return self._config
    
    def rollback(self) -> AdvancedBackchannelConfig | None:
        """Rollback to previous configuration."""
        if not self._config_history:
            logger.warning("No configuration history to rollback to")
            return None
        
        timestamp, old_config = self._config_history.pop()
        self._config = old_config
        logger.info(f"Configuration rolled back to version from {timestamp}")
        return self._config

