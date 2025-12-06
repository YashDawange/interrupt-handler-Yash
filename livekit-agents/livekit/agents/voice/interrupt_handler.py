"""
Intelligent Interruption Handler for LiveKit Agents

This module provides context-aware filtering to distinguish between:
- Filler words (yeah, okay, hmm) → IGNORE when agent is speaking
- Real commands (stop, wait, no) → INTERRUPT immediately
- Mixed input (yeah but wait) → INTERRUPT (contains real command)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Set

logger = logging.getLogger("interrupt-handler")


class AgentState(Enum):
    """Track whether agent is currently speaking or silent."""
    SPEAKING = "speaking"
    SILENT = "silent"


@dataclass
class InterruptionConfig:
    """Configuration for intelligent interruption detection."""
    
    filler_words: Set[str]
    interrupt_words: Set[str]
    min_words_for_interrupt: int

    @classmethod
    def from_json(cls, config_path: str | Path | None = None) -> "InterruptionConfig":
        """
        Load configuration from JSON file.
        
        Args:
            config_path: Path to JSON config file. 
                        If None, looks for 'interrupt_config.json' in project root.
        
        Returns:
            InterruptionConfig instance loaded from JSON
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid JSON or missing required fields
        """
        if config_path is None:
            # Default: project root (go up from livekit-agents/livekit/agents/voice/)
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent.parent
            config_path = project_root / "interrupt_config.json"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please create interrupt_config.json in the project root with:\n"
                f"  - filler_words\n"
                f"  - interrupt_words\n"
                f"  - min_words_for_interrupt"
            )

        try:
            with config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {config_path}: {e}")

        # Validate required fields
        required_fields = ["filler_words", "interrupt_words", "min_words_for_interrupt"]
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValueError(
                f"Missing required fields in {config_path}: {missing}"
            )

        return cls(
            filler_words=set(data["filler_words"]),
            interrupt_words=set(data["interrupt_words"]),
            min_words_for_interrupt=int(data["min_words_for_interrupt"]),
        )


class InterruptHandler:
    """
    Determines whether user speech should interrupt the agent.
    
    Core Logic:
    - Agent SPEAKING + only filler words → IGNORE (continue speaking)
    - Agent SPEAKING + any real word → INTERRUPT
    - Agent SILENT + any input → RESPOND (process input)
    """
    
    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize handler by loading config from JSON file.
        
        Args:
            config_path: Path to JSON config file. 
                        If None, looks for 'interrupt_config.json' in project root.
        """
        self.config = InterruptionConfig.from_json(config_path)
        self._stats = {"total": 0, "ignored": 0, "interrupted": 0}
        logger.info(
            f"Loaded config: {len(self.config.filler_words)} filler words, "
            f"{len(self.config.interrupt_words)} interrupt words"
        )
    
    def should_interrupt(
        self,
        agent_state: AgentState,
        transcribed_text: str
    ) -> bool:
        """
        Decide if the agent should be interrupted.
        
        Args:
            agent_state: Is agent currently SPEAKING or SILENT?
            transcribed_text: What the user said (from STT).
        
        Returns:
            True = interrupt the agent
            False = ignore the input, continue speaking
        """
        self._stats["total"] += 1
        
        text = transcribed_text.lower().strip()
        
        if not text:
            logger.debug("Empty transcript - ignoring")
            self._stats["ignored"] += 1
            return False
        
        words = self._tokenize(text)
        
        if not words:
            logger.debug("No valid words - ignoring")
            self._stats["ignored"] += 1
            return False
        
        # If agent is SILENT, always process user input
        if agent_state == AgentState.SILENT:
            logger.debug(f"Agent silent - processing: '{text}'")
            self._stats["interrupted"] += 1
            return True
        
        # Agent is SPEAKING - check if real interruption
        
        # Check for explicit interrupt words
        has_interrupt_word = any(
            word in self.config.interrupt_words
            for word in words
        )
        
        if has_interrupt_word:
            logger.info(f"Real interruption (interrupt word): '{text}'")
            self._stats["interrupted"] += 1
            return True
        
        # Check if ALL words are fillers
        all_fillers = all(
            word in self.config.filler_words
            for word in words
        )
        
        if all_fillers:
            logger.info(f"Ignoring filler words: '{text}'")
            self._stats["ignored"] += 1
            return False
        
        # Has non-filler words - check threshold
        non_filler_words = [
            w for w in words
            if w not in self.config.filler_words
        ]
        
        if len(non_filler_words) >= self.config.min_words_for_interrupt:
            logger.info(f"Real interruption (content): '{text}'")
            self._stats["interrupted"] += 1
            return True
        
        logger.debug(f"Single non-filler, ignoring: '{text}'")
        self._stats["ignored"] += 1
        return False
    
    def _tokenize(self, text: str) -> list[str]:
        """Split text into clean words."""
        words = re.findall(r'\b[a-z]+\b', text.lower())
        return [w for w in words if w]
    
    def get_stats(self) -> dict:
        """Get interruption statistics."""
        return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {"total": 0, "ignored": 0, "interrupted": 0}
