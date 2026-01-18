from __future__ import annotations
import os
import string
import logging
from dataclasses import dataclass
from typing import Set, Optional

logger = logging.getLogger("livekit.agents")

@dataclass(frozen=True)
class IntentAnalysis:
    """Immutable result of a semantic analysis turn."""
    allow_flow: bool
    category: str
    text: str

class IntentScorer:
    """Evaluates user vocalizations to differentiate between support and directives."""
    
    def __init__(self, soft_lexicon: Optional[Set[str]] = None, hard_directives: Optional[Set[str]] = None):
        # fetch from environment variables for modularity
        self._soft_lexicon = soft_lexicon or self._load_lexicon("AGENT_PASSIVE_LEXICON")
        self._hard_directives = hard_directives or self._load_lexicon("AGENT_DIRECTIVE_COMMANDS")

    def _load_lexicon(self, key: str) -> Set[str]:
        """Loads a comma-separated lexicon from the environment with no internal defaults."""
        raw_val = os.getenv(key)
        if not raw_val:
            logger.warning(f" IntentScorer: Environment variable {key} is missing or empty. Lexicon will be empty.")
            return set()
        
        return {word.strip().lower() for word in raw_val.split(",") if word.strip()}

    def evaluate(self, input_text: str, active_playback: bool) -> IntentAnalysis:
        # always treat input as a valid turn if the agent is silent
        if not active_playback:
            return IntentAnalysis(allow_flow=False, category="NEW_TURN", text=input_text)
            
        normalized = input_text.lower().translate(str.maketrans('', '', string.punctuation)).strip()
        tokens = normalized.split()
        
        if not tokens:
            return IntentAnalysis(allow_flow=True, category="NOISE", text=input_text)

        # check for explicit stop commands first to ensure immediate interruption
        if any(t in self._hard_directives for t in tokens):
            return IntentAnalysis(allow_flow=False, category="DIRECTIVE", text=input_text)
            
        # only allow audio flow if the entire phrase consists of passive filler words
        is_passive = all(t in self._soft_lexicon for t in tokens)
        
        return IntentAnalysis(
            allow_flow=is_passive,
            category="BACKCHANNEL" if is_passive else "VALID_INPUT",
            text=input_text
        )