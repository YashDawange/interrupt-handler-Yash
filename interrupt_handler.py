# interrupt_handler.py

from dataclasses import dataclass
from typing import List

# Words that should be ignored while agent is speaking
DEFAULT_IGNORE_WORDS = ["yeah", "ok", "okay", "hmm", "uh-huh", "right", "mm-hmm"]

# Words that clearly indicate interruption
DEFAULT_INTERRUPT_WORDS = ["stop", "wait", "no", "hold on", "cancel"]


@dataclass
class InterruptionDecision:
    """
    Result of checking a user utterance.
    """
    should_interrupt: bool       # true = cut the agent NOW
    should_ignore: bool          # true = ignore completely
    reason: str                  # short explanation for logging


class InterruptionHandler:
    """
    Core logic layer:
    - Looks at user transcript
    - Looks at whether agent is currently speaking
    - Decides whether to ignore / interrupt / treat as normal input
    """

    def __init__(
        self,
        ignore_words: List[str] | None = None,
        interrupt_words: List[str] | None = None,
    ):
        self.ignore_words = [w.lower() for w in (ignore_words or DEFAULT_IGNORE_WORDS)]
        self.interrupt_words = [w.lower() for w in (interrupt_words or DEFAULT_INTERRUPT_WORDS)]

    def _normalize(self, text: str) -> str:
        return text.strip().lower()

    def decide(self, user_text: str, agent_is_speaking: bool) -> InterruptionDecision:
        """
        Main decision function.

        Parameters:
            user_text: STT transcript of user's latest utterance.
            agent_is_speaking: True if TTS is currently playing, False if agent is silent.

        Returns:
            InterruptionDecision
        """
        text = self._normalize(user_text)

        if not text:
            return InterruptionDecision(
                should_interrupt=False,
                should_ignore=True,
                reason="empty_text",
            )

        # Mixed sentences check first: "yeah wait a second", "ok but stop"
        contains_interrupt = any(word in text for word in self.interrupt_words)
        contains_ignore = any(word in text for word in self.ignore_words)

        # CASE 1: Agent is speaking
        if agent_is_speaking:
            if contains_interrupt:
                # e.g. "yeah wait", "no stop", "ok but hold on"
                return InterruptionDecision(
                    should_interrupt=True,
                    should_ignore=False,
                    reason="agent_speaking_mixed_or_interrupt_word",
                )

            # Only filler / backchannel
            if contains_ignore and not contains_interrupt:
                # "yeah", "ok", "hmm" while agent talking
                return InterruptionDecision(
                    should_interrupt=False,
                    should_ignore=True,
                    reason="agent_speaking_backchannel",
                )

            # Any other meaningful sentence while agent is speaking → treat as interruption
            return InterruptionDecision(
                should_interrupt=True,
                should_ignore=False,
                reason="agent_speaking_meaningful_interrupt",
            )

        # CASE 2: Agent is silent
        else:
            # If agent is silent, NEVER ignore — even "yeah" might be an answer
            if contains_ignore and not contains_interrupt and len(text.split()) <= 3:
                # short passive affirmation we should respond to
                return InterruptionDecision(
                    should_interrupt=False,
                    should_ignore=False,
                    reason="agent_silent_short_ack",
                )

            if contains_interrupt:
                # "no", "stop", "wait" when silent → still a valid intent
                return InterruptionDecision(
                    should_interrupt=False,
                    should_ignore=False,
                    reason="agent_silent_command",
                )

            # Normal text input when agent silent
            return InterruptionDecision(
                should_interrupt=False,
                should_ignore=False,
                reason="agent_silent_normal_input",
            )
