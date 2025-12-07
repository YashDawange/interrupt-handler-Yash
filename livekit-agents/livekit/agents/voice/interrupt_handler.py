# """
# Intelligent Interruption Handler for LiveKit Agents

# This module provides context-aware filtering to distinguish between:
# - Filler words (yeah, okay, hmm) → IGNORE when agent is speaking
# - Real commands (stop, wait, no) → INTERRUPT immediately
# - Mixed input (yeah but wait) → INTERRUPT (contains real command)
# """

# from __future__ import annotations

# import json
# import logging
# import re
# from dataclasses import dataclass
# from enum import Enum
# from pathlib import Path
# from typing import Set

# logger = logging.getLogger("interrupt-handler")


# class AgentState(Enum):
#     """Track whether agent is currently speaking or silent."""
#     SPEAKING = "speaking"
#     SILENT = "silent"


# @dataclass
# class InterruptionConfig:
#     """Configuration for intelligent interruption detection."""
    
#     filler_words: Set[str]
#     interrupt_words: Set[str]
#     min_words_for_interrupt: int

#     @classmethod
#     def from_json(cls, config_path: str | Path | None = None) -> "InterruptionConfig":
#         """
#         Load configuration from JSON file.
        
#         Args:
#             config_path: Path to JSON config file. 
#                         If None, looks for 'interrupt_config.json' in project root.
        
#         Returns:
#             InterruptionConfig instance loaded from JSON
        
#         Raises:
#             FileNotFoundError: If config file doesn't exist
#             ValueError: If config file is invalid JSON or missing required fields
#         """
#         if config_path is None:
#             # Default: project root (go up from livekit-agents/livekit/agents/voice/)
#             current_file = Path(__file__).resolve()
#             project_root = current_file.parent.parent.parent.parent.parent
#             config_path = project_root / "interrupt_config.json"
#         else:
#             config_path = Path(config_path)

#         if not config_path.exists():
#             raise FileNotFoundError(
#                 f"Configuration file not found: {config_path}\n"
#                 f"Please create interrupt_config.json in the project root with:\n"
#                 f"  - filler_words\n"
#                 f"  - interrupt_words\n"
#                 f"  - min_words_for_interrupt"
#             )

#         try:
#             with config_path.open("r", encoding="utf-8") as f:
#                 data = json.load(f)
#         except json.JSONDecodeError as e:
#             raise ValueError(f"Invalid JSON in {config_path}: {e}")

#         # Validate required fields
#         required_fields = ["filler_words", "interrupt_words", "min_words_for_interrupt"]
#         missing = [field for field in required_fields if field not in data]
#         if missing:
#             raise ValueError(
#                 f"Missing required fields in {config_path}: {missing}"
#             )

#         return cls(
#             filler_words=set(data["filler_words"]),
#             interrupt_words=set(data["interrupt_words"]),
#             min_words_for_interrupt=int(data["min_words_for_interrupt"]),
#         )


# class InterruptHandler:
#     """
#     Determines whether user speech should interrupt the agent.
    
#     Core Logic:
#     - Agent SPEAKING + only filler words → IGNORE (continue speaking)
#     - Agent SPEAKING + any real word → INTERRUPT
#     - Agent SILENT + any input → RESPOND (process input)
#     """
    
#     def __init__(self, config_path: str | Path | None = None):
#         """
#         Initialize handler by loading config from JSON file.
        
#         Args:
#             config_path: Path to JSON config file. 
#                         If None, looks for 'interrupt_config.json' in project root.
#         """
#         self.config = InterruptionConfig.from_json(config_path)
#         self._stats = {"total": 0, "ignored": 0, "interrupted": 0}
#         logger.info(
#             f"Loaded config: {len(self.config.filler_words)} filler words, "
#             f"{len(self.config.interrupt_words)} interrupt words"
#         )
    
#     def should_interrupt(
#         self,
#         agent_state: AgentState,
#         transcribed_text: str
#     ) -> bool:
#         """
#         Decide if the agent should be interrupted.
        
#         Args:
#             agent_state: Is agent currently SPEAKING or SILENT?
#             transcribed_text: What the user said (from STT).
        
#         Returns:
#             True = interrupt the agent
#             False = ignore the input, continue speaking
#         """
#         self._stats["total"] += 1
        
#         text = transcribed_text.lower().strip()
        
#         if not text:
#             logger.debug("Empty transcript - ignoring")
#             self._stats["ignored"] += 1
#             return False
        
#         words = self._tokenize(text)
        
#         if not words:
#             logger.debug("No valid words - ignoring")
#             self._stats["ignored"] += 1
#             return False
        
#         # If agent is SILENT, always process user input
#         if agent_state == AgentState.SILENT:
#             logger.debug(f"Agent silent - processing: '{text}'")
#             self._stats["interrupted"] += 1
#             return True
        
#         # Agent is SPEAKING - check if real interruption
        
#         # Check for explicit interrupt words
#         has_interrupt_word = any(
#             word in self.config.interrupt_words
#             for word in words
#         )
        
#         if has_interrupt_word:
#             logger.info(f"Real interruption (interrupt word): '{text}'")
#             self._stats["interrupted"] += 1
#             return True
        
#         # Check if ALL words are fillers
#         all_fillers = all(
#             word in self.config.filler_words
#             for word in words
#         )
        
#         if all_fillers:
#             logger.info(f"Ignoring filler words: '{text}'")
#             self._stats["ignored"] += 1
#             return False
        
#         # Has non-filler words - check threshold
#         non_filler_words = [
#             w for w in words
#             if w not in self.config.filler_words
#         ]
        
#         if len(non_filler_words) >= self.config.min_words_for_interrupt:
#             logger.info(f"Real interruption (content): '{text}'")
#             self._stats["interrupted"] += 1
#             return True
        
#         logger.debug(f"Single non-filler, ignoring: '{text}'")
#         self._stats["ignored"] += 1
#         return False
    
#     def _tokenize(self, text: str) -> list[str]:
#         """Split text into clean words."""
#         words = re.findall(r'\b[a-z]+\b', text.lower())
#         return [w for w in words if w]
    
#     def get_stats(self) -> dict:
#         """Get interruption statistics."""
#         return self._stats.copy()
    
#     def reset_stats(self) -> None:
#         """Reset statistics."""
#         self._stats = {"total": 0, "ignored": 0, "interrupted": 0}






"""
Smart interruption logic for LiveKit agents.

Goal:
  - Treat short backchannel words ("yeah", "ok") as filler while the assistant speaks.
  - Treat explicit commands ("stop", "wait") or sufficiently long non-filler input as
    a real interruption that should stop TTS and be processed immediately.

This file intentionally preserves the same external names:
  - InterruptHandler.should_interrupt(agent_state, text) -> bool
  - AgentState (Enum with SPEAKING / SILENT)
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

# -------------------------
# Public state enum
# -------------------------
class AgentState(Enum):
    """High-level speaking state used by interruption checks."""
    SPEAKING = "speaking"
    SILENT = "silent"


@dataclass
class InterruptionConfig:
    """Configuration holder for filler vs interrupt words and thresholds."""
    filler_words: Set[str]
    interrupt_words: Set[str]
    min_words_for_interrupt: int

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> "InterruptionConfig":
        """
        Load config from JSON. If `path` is omitted, looks for project-root
        `interrupt_config.json`. Raises FileNotFoundError / ValueError for problems.
        """
        if path is None:
            current = Path(__file__).resolve()
            # project root heuristic: go up until you leave the package
            project_root = current.parent.parent.parent.parent.parent
            path = project_root / "interrupt_config.json"
        else:
            path = Path(path)

        if not path.exists():
            raise FileNotFoundError(
                f"Missing interruption configuration at: {path}\n"
                "Create an interrupt_config.json with keys: "
                "filler_words, interrupt_words, min_words_for_interrupt"
            )

        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as err:
            raise ValueError(f"Invalid JSON in {path}: {err}")

        required = ["filler_words", "interrupt_words", "min_words_for_interrupt"]
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"interrupt_config.json missing fields: {missing}")

        return cls(
            filler_words=set(data["filler_words"]),
            interrupt_words=set(data["interrupt_words"]),
            min_words_for_interrupt=int(data["min_words_for_interrupt"]),
        )


class InterruptHandler:
    """
    Small, deterministic handler that decides whether incoming STT text should
    interrupt currently-playing TTS.

    API:
      - should_interrupt(agent_state: AgentState, transcribed_text: str) -> bool
      - _tokenize(text) -> list[str]   (kept for compatibility / debugging)
      - get_stats(), reset_stats()
    """

    def __init__(self, config_path: str | Path | None = None):
        self.config = InterruptionConfig.from_json(config_path)
        self._counts = {"total": 0, "ignored": 0, "interrupted": 0}
        logger.info(
            "InterruptHandler initialized: %d filler words, %d interrupt words",
            len(self.config.filler_words),
            len(self.config.interrupt_words),
        )

    def should_interrupt(self, agent_state: AgentState, transcribed_text: str) -> bool:
        """
        Return True when we should stop the assistant's speech and handle the input.
        The decision policy:
          - If assistant is SILENT => always treat as input (True).
          - If assistant is SPEAKING:
              * If any explicit interrupt word present => True.
              * If all tokens are filler => False.
              * If there are >= min_words_for_interrupt non-filler tokens => True.
              * Otherwise => False.
        """
        self._counts["total"] += 1

        text = (transcribed_text or "").lower().strip()
        if not text:
            logger.debug("Empty transcript received — ignoring")
            self._counts["ignored"] += 1
            return False

        words = self._tokenize(text)
        if not words:
            logger.debug("No valid tokens after tokenization — ignoring")
            self._counts["ignored"] += 1
            return False

        # If assistant is not speaking, always process the input
        if agent_state == AgentState.SILENT:
            logger.debug("Assistant silent — processing input")
            self._counts["interrupted"] += 1
            return True

        # When assistant is speaking:
        # 1) explicit interrupt words (highest priority)
        if any(w in self.config.interrupt_words for w in words):
            logger.info("Interrupt detected by explicit word: %s", text)
            self._counts["interrupted"] += 1
            return True

        # 2) if all tokens are filler/backchannel words -> ignore
        if all(w in self.config.filler_words for w in words):
            logger.info("Filler-only utterance — ignoring: %s", text)
            self._counts["ignored"] += 1
            return False

        # 3) count non-filler words, interrupt if they meet threshold
        non_fillers = [w for w in words if w not in self.config.filler_words]
        if len(non_fillers) >= self.config.min_words_for_interrupt:
            logger.info("Contentful interruption (threshold): %s", text)
            self._counts["interrupted"] += 1
            return True

        # Otherwise treat as a short/non-interrupting utterance
        logger.debug("Short/non-interrupting utterance — ignoring: %s", text)
        self._counts["ignored"] += 1
        return False

    def _tokenize(self, text: str) -> list[str]:
        """Return lowercase alphabetic tokens (simple, fast tokenizer)."""
        return [tok for tok in re.findall(r"\b[a-z]+\b", (text or "").lower())]

    def get_stats(self) -> dict:
        """Return a snapshot of internal counters."""
        return dict(self._counts)

    def reset_stats(self) -> None:
        """Reset the internal counters to zero."""
        self._counts = {"total": 0, "ignored": 0, "interrupted": 0}