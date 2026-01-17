"""
Configuration Loader for Interruption Handler

Loads interruption handler configuration from:
1. Environment variables
2. Configuration JSON file
3. Programmatic defaults

This allows users to customize behavior without code changes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...log import logger


@dataclass
class InterruptionHandlerConfig:
    """Configuration for interruption handler."""
    
    enabled: bool = True
    """Enable/disable interruption handling."""
    
    ignore_words: list[str] = None
    """Words to ignore when agent is speaking (backchanneling)."""
    
    command_words: list[str] = None
    """Words that trigger immediate interruption."""
    
    fuzzy_matching_enabled: bool = True
    """Enable fuzzy matching for typos."""
    
    fuzzy_threshold: float = 0.8
    """Similarity threshold for fuzzy matching (0.0 - 1.0)."""
    
    stt_wait_timeout_ms: float = 500.0
    """Maximum wait time for STT transcription in milliseconds."""
    
    wait_for_transcription: bool = True
    """Wait for STT before making interruption decision."""
    
    verbose_logging: bool = False
    """Enable verbose logging for debugging."""
    
    log_all_decisions: bool = False
    """Log all interruption decisions."""
    
    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.ignore_words is None:
            self.ignore_words = [
                "yeah",
                "ok",
                "okay",
                "hmm",
                "uh-huh",
                "uhhuh",
                "right",
                "yep",
                "mm-hmm",
                "mhmm",
                "uh",
                "um",
                "sure",
                "got it",
                "gotcha",
                "i hear you",
                "i see",
                "understood",
                "copy that",
                "yup",
                "ya",
            ]
        
        if self.command_words is None:
            self.command_words = [
                "stop",
                "wait",
                "no",
                "hold on",
                "hold up",
                "pause",
                "slow down",
                "hold",
                "dont",
                "don't",
                "never mind",
                "never",
                "wrong",
                "nope",
                "cancel",
                "abort",
                "quit",
                "exit",
                "end",
            ]
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "ignore_words": self.ignore_words,
            "command_words": self.command_words,
            "fuzzy_matching_enabled": self.fuzzy_matching_enabled,
            "fuzzy_threshold": self.fuzzy_threshold,
            "stt_wait_timeout_ms": self.stt_wait_timeout_ms,
            "wait_for_transcription": self.wait_for_transcription,
            "verbose_logging": self.verbose_logging,
            "log_all_decisions": self.log_all_decisions,
        }


class ConfigLoader:
    """
    Load interruption handler configuration from multiple sources.
    
    Priority order (highest to lowest):
    1. Environment variables
    2. Configuration file (JSON)
    3. Programmatic defaults
    """
    
    # Environment variable prefixes
    ENV_PREFIX = "LIVEKIT_INTERRUPTION_"
    ENV_IGNORE_WORDS = f"{ENV_PREFIX}IGNORE_WORDS"
    ENV_COMMAND_WORDS = f"{ENV_PREFIX}COMMAND_WORDS"
    ENV_FUZZY_ENABLED = f"{ENV_PREFIX}FUZZY_ENABLED"
    ENV_FUZZY_THRESHOLD = f"{ENV_PREFIX}FUZZY_THRESHOLD"
    ENV_STT_TIMEOUT = f"{ENV_PREFIX}STT_TIMEOUT_MS"
    ENV_WAIT_FOR_STT = f"{ENV_PREFIX}WAIT_FOR_TRANSCRIPTION"
    ENV_VERBOSE = f"{ENV_PREFIX}VERBOSE_LOGGING"
    ENV_LOG_DECISIONS = f"{ENV_PREFIX}LOG_ALL_DECISIONS"
    ENV_CONFIG_FILE = f"{ENV_PREFIX}CONFIG_FILE"
    
    @staticmethod
    def load_from_env() -> InterruptionHandlerConfig:
        """
        Load configuration from environment variables.
        
        Returns:
            InterruptionHandlerConfig: Config loaded from environment.
        """
        config = InterruptionHandlerConfig()
        
        # Check for config file path
        config_file = os.getenv(ConfigLoader.ENV_CONFIG_FILE)
        if config_file:
            loaded = ConfigLoader.load_from_file(config_file)
            if loaded:
                config = loaded
        
        # Override with individual environment variables
        ignore_words_env = os.getenv(ConfigLoader.ENV_IGNORE_WORDS)
        if ignore_words_env:
            config.ignore_words = ConfigLoader._parse_word_list(ignore_words_env)
            logger.debug(f"Loaded ignore_words from env: {len(config.ignore_words)} words")
        
        command_words_env = os.getenv(ConfigLoader.ENV_COMMAND_WORDS)
        if command_words_env:
            config.command_words = ConfigLoader._parse_word_list(command_words_env)
            logger.debug(f"Loaded command_words from env: {len(config.command_words)} words")
        
        fuzzy_enabled = os.getenv(ConfigLoader.ENV_FUZZY_ENABLED)
        if fuzzy_enabled:
            config.fuzzy_matching_enabled = fuzzy_enabled.lower() in ("true", "1", "yes")
        
        fuzzy_threshold = os.getenv(ConfigLoader.ENV_FUZZY_THRESHOLD)
        if fuzzy_threshold:
            try:
                config.fuzzy_threshold = float(fuzzy_threshold)
            except ValueError:
                logger.warning(f"Invalid fuzzy_threshold: {fuzzy_threshold}")
        
        stt_timeout = os.getenv(ConfigLoader.ENV_STT_TIMEOUT)
        if stt_timeout:
            try:
                config.stt_wait_timeout_ms = float(stt_timeout)
            except ValueError:
                logger.warning(f"Invalid stt_wait_timeout_ms: {stt_timeout}")
        
        wait_for_stt = os.getenv(ConfigLoader.ENV_WAIT_FOR_STT)
        if wait_for_stt:
            config.wait_for_transcription = wait_for_stt.lower() in ("true", "1", "yes")
        
        verbose = os.getenv(ConfigLoader.ENV_VERBOSE)
        if verbose:
            config.verbose_logging = verbose.lower() in ("true", "1", "yes")
        
        log_decisions = os.getenv(ConfigLoader.ENV_LOG_DECISIONS)
        if log_decisions:
            config.log_all_decisions = log_decisions.lower() in ("true", "1", "yes")
        
        return config
    
    @staticmethod
    def load_from_file(file_path: str | Path) -> Optional[InterruptionHandlerConfig]:
        """
        Load configuration from JSON file.
        
        Args:
            file_path: Path to configuration JSON file.
        
        Returns:
            InterruptionHandlerConfig: Config loaded from file, or None if not found.
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.warning(f"Configuration file not found: {file_path}")
            return None
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            # Extract interruption_handling section
            interrupt_config = data.get("interruption_handling", {})
            
            config = InterruptionHandlerConfig()
            
            if "enabled" in interrupt_config:
                config.enabled = interrupt_config["enabled"]
            
            if "ignore_words" in interrupt_config:
                ignore_section = interrupt_config["ignore_words"]
                if isinstance(ignore_section, dict) and "words" in ignore_section:
                    config.ignore_words = ignore_section["words"]
                elif isinstance(ignore_section, list):
                    config.ignore_words = ignore_section
            
            if "command_words" in interrupt_config:
                command_section = interrupt_config["command_words"]
                if isinstance(command_section, dict) and "words" in command_section:
                    config.command_words = command_section["words"]
                elif isinstance(command_section, list):
                    config.command_words = command_section
            
            fuzzy = interrupt_config.get("fuzzy_matching", {})
            if "enabled" in fuzzy:
                config.fuzzy_matching_enabled = fuzzy["enabled"]
            if "similarity_threshold" in fuzzy:
                config.fuzzy_threshold = fuzzy["similarity_threshold"]
            
            timeout = interrupt_config.get("timeout_settings", {})
            if "stt_wait_timeout_ms" in timeout:
                config.stt_wait_timeout_ms = timeout["stt_wait_timeout_ms"]
            
            vad_stt = interrupt_config.get("vad_stt_sync", {})
            if "wait_for_transcription" in vad_stt:
                config.wait_for_transcription = vad_stt["wait_for_transcription"]
            
            logging_config = interrupt_config.get("logging", {})
            if "verbose" in logging_config:
                config.verbose_logging = logging_config["verbose"]
            if "log_all_decisions" in logging_config:
                config.log_all_decisions = logging_config["log_all_decisions"]
            
            logger.info(f"Loaded configuration from {file_path}")
            return config
        
        except Exception as e:
            logger.error(f"Error loading configuration from {file_path}: {e}")
            return None
    
    @staticmethod
    def _parse_word_list(word_string: str) -> list[str]:
        """
        Parse comma-separated word list from string.
        
        Args:
            word_string: Comma-separated words or JSON array string.
        
        Returns:
            list[str]: Parsed word list.
        """
        # Try JSON array format first
        if word_string.startswith("["):
            try:
                return json.loads(word_string)
            except json.JSONDecodeError:
                pass
        
        # Fall back to comma-separated
        words = [w.strip() for w in word_string.split(",")]
        return [w for w in words if w]
    
    @staticmethod
    def get_default_config() -> InterruptionHandlerConfig:
        """
        Get default configuration.
        
        Returns:
            InterruptionHandlerConfig: Default configuration.
        """
        return InterruptionHandlerConfig()


def load_config(
    config_file: Optional[str | Path] = None,
    from_env: bool = True,
) -> InterruptionHandlerConfig:
    """
    Load configuration with priority order.
    
    Args:
        config_file: Optional explicit config file path.
        from_env: Whether to check environment variables (default: True).
    
    Returns:
        InterruptionHandlerConfig: Loaded configuration.
    """
    config = InterruptionHandlerConfig()
    
    # Load from explicit file if provided
    if config_file:
        loaded = ConfigLoader.load_from_file(config_file)
        if loaded:
            config = loaded
    
    # Override with environment variables
    if from_env:
        config = ConfigLoader.load_from_env()
    
    return config
