from enum import Enum, auto
from .intent_controller import Intent
from .context import ConversationContext


class Action(Enum):
    IGNORE = auto()
    INTERRUPT = auto()
    PASS = auto()


class ContextAwarePolicy:
    """
    Decides action using intent + conversation context.
    """

    def decide(self, intent: Intent, ctx: ConversationContext) -> Action:
        if ctx.agent_speaking:
          if intent == Intent.INTERRUPT:
            return Action.INTERRUPT
          if intent == Intent.BACKCHANNEL:
            return Action.IGNORE
        return Action.PASS

    # Agent silent
        if not ctx.agent_speaking:
          if intent in (Intent.START, Intent.BACKCHANNEL):
            return Action.PASS  # allow agent to respond normally

        return Action.PASS
