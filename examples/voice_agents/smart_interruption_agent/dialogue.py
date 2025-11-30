import re
import os
from enum import Enum
from typing import Set, List

from config import AgentConfig
from utils import Logger

class UserIntent(Enum):
    BACKCHANNEL = "backchannel"
    COMMAND = "command"
    QUERY = "query"

class TurnStrategy(Enum):
    IGNORE = "ignore"
    INTERRUPT = "interrupt"
    INTERRUPT_AND_RESPOND = "interrupt_and_respond"
    RESPOND = "respond"
    WAIT = "wait"

class SpeechIntentClassifier:
    """Classifies user speech into intents."""
    
    # Default patterns for backchannels
    DEFAULT_BACKCHANNELS = {
        "yeah", "yep", "ok", "okay", "hmm", "mm", "uh", "uhh", "uh-huh",
        "right", "alright", "aha", "got", "it", "sure", "mhm", "yup", "ooh",
        "cool", "nice", "interesting"
    }
    
    # Default patterns for commands
    DEFAULT_COMMANDS = {
        "wait", "stop", "no", "cancel", "pause", "hold", "nevermind",
        "never", "mind", "whoa", "shut", "quiet", "enough", "silence"
    }

    def __init__(self):
        self._backchannels = self._load_words("BACKCHANNEL_WORDS", self.DEFAULT_BACKCHANNELS)
        self._commands = self._load_words("COMMAND_WORDS", self.DEFAULT_COMMANDS)
        
        # Pre-compile regex for efficiency if needed, but simple set lookup is fast for words
        # We can add regex patterns for more complex backchannels if needed
        self._backchannel_patterns = [
            re.compile(r"^yeah\.?\s*$", re.IGNORECASE),
            re.compile(r"^ok(ay)?\.?\s*$", re.IGNORECASE),
            re.compile(r"^hmm+\.?\s*$", re.IGNORECASE),
            re.compile(r"^uh\s*-?huh\.?\s*$", re.IGNORECASE),
        ]

    def _load_words(self, env_var: str, defaults: Set[str]) -> Set[str]:
        env_val = os.getenv(env_var, "")
        if env_val.strip():
            return {w.strip().lower() for w in env_val.split(",") if w.strip()}
        return defaults

    def classify(self, text: str) -> UserIntent:
        if not text or not text.strip():
            return UserIntent.BACKCHANNEL
            
        normalized = text.strip().lower()
        
        # Check regex patterns first for exact matches of common backchannels
        if any(p.match(normalized) for p in self._backchannel_patterns):
            return UserIntent.BACKCHANNEL
            
        # Tokenize
        tokens = set(re.sub(r"[.,!?;:\-]", " ", normalized).split())
        
        # Analyze tokens
        has_command = any(w in self._commands for w in tokens)
        
        if has_command:
            # If ANY command word is present, treat as COMMAND to ensure immediate interruption.
            # We prioritize stopping over analyzing the rest of the sentence.
            return UserIntent.COMMAND
        
        # Check if ALL tokens are backchannel words
        if tokens and all(t in self._backchannels for t in tokens):
             return UserIntent.BACKCHANNEL
             
        return UserIntent.QUERY

class TurnManager:
    """Decides on the turn-taking strategy."""
    
    def __init__(self, config: AgentConfig, logger: Logger):
        self.config = config
        self.logger = logger

    def decide_strategy(self, intent: UserIntent, is_agent_speaking: bool, is_final_transcript: bool, time_since_interrupt: float = 999.0) -> TurnStrategy:
        """
        Determine how to handle the user input based on context.
        """
        if is_agent_speaking:
            if intent == UserIntent.BACKCHANNEL:
                self.logger.log_decision("IGNORE", "Backchannel detected while speaking")
                return TurnStrategy.IGNORE
                
            if intent == UserIntent.COMMAND:
                self.logger.log_decision("INTERRUPT", "Command detected while speaking")
                return TurnStrategy.INTERRUPT
                
            if not is_final_transcript:
                # If it's a query but not final, wait for more context
                self.logger.log_decision("WAIT", "Interim query while speaking")
                return TurnStrategy.WAIT
                
            # Final query while speaking -> Interrupt and answer
            self.logger.log_decision("INTERRUPT_AND_RESPOND", "Final query while speaking")
            return TurnStrategy.INTERRUPT_AND_RESPOND
            
        else:
            # Agent is listening
            if intent == UserIntent.COMMAND:
                # If we just interrupted, ignore the tail of the command (e.g. "No stop" -> "Stop" caused interrupt, "No stop" is tail)
                if time_since_interrupt < 2.0:
                    self.logger.log_decision("IGNORE", f"Ignoring command '{intent}' immediately after interruption ({time_since_interrupt:.2f}s)")
                    return TurnStrategy.IGNORE
                
                # Otherwise, if it's a standalone command while silent (e.g. "Stop" when already stopped),
                # we probably shouldn't respond "Ok stopping". Just ignore.
                self.logger.log_decision("IGNORE", "Command while already silent")
                return TurnStrategy.IGNORE

            if is_final_transcript:
                self.logger.log_decision("RESPOND", "Final input while listening")
                return TurnStrategy.RESPOND
            
            self.logger.log_decision("WAIT", "Interim input while listening")
            return TurnStrategy.WAIT
