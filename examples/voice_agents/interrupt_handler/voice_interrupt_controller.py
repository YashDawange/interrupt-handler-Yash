import re
from typing import Optional

from .intent_controller import IntentClassifier, Intent
from .interruption_policy import ContextAwarePolicy, Action
from .context import ConversationContext

NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    return NORMALIZE_RE.sub(" ", text.lower()).strip()


class ContextAwareVoiceController:
    """
    Glue layer:
    - Tracks agent state
    - Normalizes text
    - Classifies intent
    - Applies policy
    """

    def __init__(
        self,
        classifier: IntentClassifier,
        policy: ContextAwarePolicy,
    ) -> None:
        self._classifier = classifier
        self._policy = policy
        self._agent_speaking: bool = False
        self._last_intent: Optional[Intent] = None

    def update_agent_state(self, new_state: str) -> None:
        self._agent_speaking = new_state == "speaking"

    def handle_transcript(self, transcript: str, is_final: bool) -> Action:
        if not transcript:
            return Action.PASS

        text = normalize(transcript)
        intent = self._classifier.classify(text)

        ctx = ConversationContext(
            agent_speaking=self._agent_speaking,
            is_final_transcript=is_final,
            last_user_intent=self._last_intent,
        )

        action = self._policy.decide(intent, ctx)

        if is_final:
            self._last_intent = intent

        return action
