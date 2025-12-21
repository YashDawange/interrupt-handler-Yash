from dataclasses import dataclass
from typing import Optional
from .intent_controller import Intent


@dataclass
class ConversationContext:
    agent_speaking: bool
    is_final_transcript: bool
    last_user_intent: Optional[Intent] = None
