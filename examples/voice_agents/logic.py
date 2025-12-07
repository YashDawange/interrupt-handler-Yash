import json
import re
import logging
from enum import Enum
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("logic-engine")

class AgentState(Enum):
    SILENT = "silent"
    SPEAKING = "speaking"

class Action(Enum):
    IGNORE_AND_RESUME = "ignore_resume"  # Ignore filler, keep talking
    INTERRUPT = "interrupt"              # Stop talking, handle command
    RESPOND = "respond"                  # Normal conversation

@dataclass
class Config:
    fillers: set
    commands: set
    min_words: int

class InterruptHandler:
    def __init__(self, config_path="interrupt_config.json"):
        self.config = self._load_config(config_path)

    def _load_config(self, filename):
        current_dir = Path(__file__).parent
        root_dir = current_dir.parent.parent
        path = root_dir / filename
        
        if not path.exists():
            logger.warning(f"Config not found at {path}. Using defaults.")
            return Config(
                fillers={"yeah", "ok", "uh-huh"}, 
                commands={"stop", "wait"}, 
                min_words=2
            )
            
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return Config(
                    fillers=set(data.get("filler_words", [])),
                    commands=set(data.get("command_words", [])),
                    min_words=data.get("min_words_for_interrupt", 2)
                )
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return Config(fillers=set(), commands=set(), min_words=2)

    def decide_action(self, agent_state: AgentState, text: str) -> Action:
        """
        Determines the correct Action based on the Logic Matrix.
        """
        clean_text = text.lower().strip()
        if not clean_text:
             return Action.IGNORE_AND_RESUME

        # Tokenize (split by non-word characters)
        words = re.findall(r'\w+', clean_text)
        
        if not words:
            return Action.IGNORE_AND_RESUME

        # [cite_start]SCENARIO 1: Agent is Silent -> Always Respond [cite: 34-35]
        if agent_state == AgentState.SILENT:
            return Action.RESPOND

        # SCENARIO 2: Agent is Speaking
        # [cite_start]Check for commands (Priority 1) [cite: 21-23]
        if any(w in self.config.commands for w in words):
            return Action.INTERRUPT

        # [cite_start]Check for pure backchannel (Priority 2) [cite: 18-20]
        is_pure_backchannel = all(w in self.config.fillers for w in words)
        if is_pure_backchannel:
            return Action.IGNORE_AND_RESUME

        # [cite_start]Check word count threshold (Priority 3) [cite: 39-40]
        # "Yeah but why" -> 3 words (Interrupt) vs "Yeah" -> 1 word (Ignore)
        non_fillers = [w for w in words if w not in self.config.fillers]
        
        # If ambiguous short sentence without explicit commands, err on side of ignore
        if len(non_fillers) < self.config.min_words:
             return Action.IGNORE_AND_RESUME
             
        return Action.INTERRUPT