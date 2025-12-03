"""Context-aware interrupt handler for intelligent interruption detection.

This module provides intelligent filtering of user interruptions based on:
1. Agent state (speaking vs silent)
2. User input classification (backchannel signals vs actual commands)
3. Configurable word lists for backchannels and commands

The handler prevents false positive interruptions from backchannel signals
(like "yeah", "okay", "hmm") when the agent is speaking, while still allowing
genuine interruptions and commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

__all__ = [
    "InterruptAction",
    "InterruptHandler",
    "InterruptAnalysis",
]


class InterruptAction(str, Enum):
    """Action to take for a detected interrupt."""

    IGNORE = "ignore"  # Ignore the interrupt (backchannel only)
    INTERRUPT = "interrupt"  # Process the interrupt (user wants agent to stop)
    RESPOND = "respond"  # User is not interrupting (agent is silent)


@dataclass
class InterruptAnalysis:
    """Result of interrupt analysis."""

    action: InterruptAction
    is_backchannel_only: bool
    has_command_words: bool
    matched_words: list[str]
    confidence: float  # 0.0 to 1.0


class InterruptHandler:
    """Intelligent interrupt handler for agent sessions.

    Analyzes user input to classify interruptions as:
    - Backchannel signals: Acknowledging signals that don't require interruption
    - Command words: Direct instructions to stop or change agent behavior
    - Mixed: Both backchannel and command words

    Args:
        min_interrupt_duration: Minimum duration (ms) to consider as interruption
        min_interruption_words: Minimum words to trigger an interruption
        backchannel_words: Set of words considered backchannels
        command_words: Set of words considered direct commands
    """

    # Default backchannel words - user acknowledgment signals
    # Including common STT transcription variations
    DEFAULT_BACKCHANNEL_WORDS = {
        # Yeah variations (STT often transcribes differently)
        "yeah",
        "yea",
        "ya",
        "yah",
        "yeh",
        "yeaah",
        "yeahh",
        # Yes variations
        "yep",
        "yup",
        "yes",
        "yess",
        # Okay variations (STT often transcribes differently)
        "okay",
        "ok",
        "okey",
        "okk",
        "kay",
        "k",
        "kk",
        "okaay",
        "alright",
        "all right",
        "aight",
        # Sure variations
        "sure",
        "for sure",
        "sure thing",
        # Acknowledgment sounds
        "uh-huh",
        "uh huh",
        "uhuh",
        "mm-hmm",
        "mm hmm",
        "mmhmm",
        "mhm",
        "mmm",
        "hmm",
        "hm",
        "hmmm",
        "uh",
        "uhh",
        "uhhh",
        "um",
        "umm",
        "ummm",
        "ah",
        "ahh",
        "oh",
        "ohh",
        # Right variations
        "right",
        "rite",
        # Understanding/agreement phrases
        "i see",
        "i got it",
        "got it",
        "gotcha",
        "makes sense",
        "understood",
        "copy that",
        "all good",
        "perfect",
        "nice",
        "cool",
        "great",
        "awesome",
        "interesting",
        "no problem",
        "you're right",
        "that's right",
        "i agree",
        "totally",
        "exactly",
        "absolutely",
        "definitely",
        "indeed",
        "quite",
        "go ahead",
        "please continue",
        "go on",
        "continue",
    }

    # Default command words - direct instructions to agent
    DEFAULT_COMMAND_WORDS = {
        "wait",
        "hold on",
        "stop",
        "pause",
        "hold it",
        "hold up",
        "no",
        "nope",
        "don't",
        "don't do that",
        "cancel",
        "never mind",
        "never",
        "forget it",
        "ignore that",
        "skip that",
        "skip it",
        "back up",
        "rewind",
        "again",
        "repeat",
        "slower",
        "faster",
        "louder",
        "quieter",
        "quieter please",
        "speak up",
        "what",
        "huh",
        "pardon",
        "come again",
        "say again",
        "say that again",
        "redo",
        "change that",
        "different",
        "something else",
        "alternative",
        "try again",
        "one more time",
        "rephrase",
        "rephrase that",
        "explain",
        "clarify",
        "say it differently",
        "summarize",
        "start over",
        "begin again",
        "let's start over",
        "restart",
    }

    def __init__(
        self,
        *,
        min_interrupt_duration: int = 200,
        min_interruption_words: int = 1,
        backchannel_words: set[str] | None = None,
        command_words: set[str] | None = None,
    ) -> None:
        """Initialize the interrupt handler.

        Args:
            min_interrupt_duration: Minimum milliseconds of speech to interrupt
            min_interruption_words: Minimum word count to trigger interrupt
            backchannel_words: Custom set of backchannel words
            command_words: Custom set of command words
        """
        self.min_interrupt_duration = min_interrupt_duration
        self.min_interruption_words = min_interruption_words

        # Initialize word sets (lowercase for case-insensitive matching)
        self.backchannel_words = set(
            word.lower() for word in (backchannel_words or self.DEFAULT_BACKCHANNEL_WORDS)
        )
        self.command_words = set(
            word.lower() for word in (command_words or self.DEFAULT_COMMAND_WORDS)
        )

    def analyze(
        self,
        transcript: str,
        agent_state: str | None = None,
        speech_duration: int | None = None,
    ) -> InterruptAnalysis:
        """Analyze a transcript for interrupt intent.

        Args:
            transcript: User's spoken text
            agent_state: Current agent state ('speaking', 'silent', 'listening', etc.)
            speech_duration: Duration of user speech in milliseconds

        Returns:
            InterruptAnalysis with action and classification details
        """
        if not transcript or not transcript.strip():
            return InterruptAnalysis(
                action=InterruptAction.RESPOND,
                is_backchannel_only=False,
                has_command_words=False,
                matched_words=[],
                confidence=0.0,
            )

        # Tokenize and lowercase
        words = [word.lower().strip(".,!?;:\"'") for word in transcript.split()]
        words = [w for w in words if w]  # Remove empty strings

        if not words:
            return InterruptAnalysis(
                action=InterruptAction.RESPOND,
                is_backchannel_only=False,
                has_command_words=False,
                matched_words=[],
                confidence=0.0,
            )

        # Find matched words (both single words and multi-word phrases)
        matched_backchannels = [w for w in words if w in self.backchannel_words]
        matched_commands = [w for w in words if w in self.command_words]

        # Check for multi-word backchannel phrases like "all right", "uh huh"
        transcript_lower = transcript.lower()
        for phrase in self.backchannel_words:
            if " " in phrase and phrase in transcript_lower:
                if phrase not in matched_backchannels:
                    matched_backchannels.append(phrase)

        # Check for multi-word command phrases like "hold on"
        for phrase in self.command_words:
            if " " in phrase and phrase in transcript_lower:
                if phrase not in matched_commands:
                    matched_commands.append(phrase)

        # Also check if the entire cleaned transcript matches a backchannel
        # This handles cases like "Yeah." -> "yeah" or "Okay!" -> "okay"
        full_cleaned = transcript_lower.strip().strip(".,!?;:\"'").strip()
        if full_cleaned in self.backchannel_words and full_cleaned not in matched_backchannels:
            matched_backchannels.append(full_cleaned)

        # Check if entire transcript matches a command
        if full_cleaned in self.command_words and full_cleaned not in matched_commands:
            matched_commands.append(full_cleaned)

        is_backchannel_only = len(matched_backchannels) > 0 and len(matched_commands) == 0
        has_command_words = len(matched_commands) > 0

        # Check minimum word threshold
        if len(words) < self.min_interruption_words:
            is_backchannel_only = False
            has_command_words = False

        # Decide action based on classification and agent state
        action = self._decide_action(
            is_backchannel_only=is_backchannel_only,
            has_command_words=has_command_words,
            agent_state=agent_state,
            speech_duration=speech_duration,
            word_count=len(words),
        )

        # Calculate confidence (0.0 to 1.0)
        confidence = self._calculate_confidence(
            action=action,
            matched_backchannels=matched_backchannels,
            matched_commands=matched_commands,
            word_count=len(words),
        )

        all_matched = matched_backchannels + matched_commands

        return InterruptAnalysis(
            action=action,
            is_backchannel_only=is_backchannel_only,
            has_command_words=has_command_words,
            matched_words=all_matched,
            confidence=confidence,
        )

    def _decide_action(
        self,
        *,
        is_backchannel_only: bool,
        has_command_words: bool,
        agent_state: str | None,
        speech_duration: int | None,
        word_count: int,
    ) -> InterruptAction:
        """Decide interrupt action based on classification and context.

        Decision logic:
        - Backchannel only + agent speaking → IGNORE
        - Command words present → INTERRUPT
        - No clear command/backchannel → RESPOND
        - Short duration or few words → RESPOND
        """
        # Check duration threshold
        if speech_duration is not None and speech_duration < self.min_interrupt_duration:
            return InterruptAction.RESPOND

        # If it's just backchannel signals, ignore when agent is speaking
        if is_backchannel_only:
            if agent_state and agent_state.lower() in ("speaking", "generating"):
                return InterruptAction.IGNORE
            # If agent is silent and user gives backchannel, respond
            return InterruptAction.RESPOND

        # If there are command words, interrupt
        if has_command_words:
            return InterruptAction.INTERRUPT

        # Default: respond (don't interrupt, but acknowledge)
        return InterruptAction.RESPOND

    def _calculate_confidence(
        self,
        *,
        action: InterruptAction,
        matched_backchannels: list[str],
        matched_commands: list[str],
        word_count: int,
    ) -> float:
        """Calculate confidence score for the action (0.0 to 1.0)."""
        if action == InterruptAction.IGNORE:
            # High confidence if pure backchannel
            return min(1.0, len(matched_backchannels) / word_count) if word_count > 0 else 0.5

        if action == InterruptAction.INTERRUPT:
            # High confidence if commands present
            return min(1.0, len(matched_commands) / word_count) if word_count > 0 else 0.7

        # RESPOND action - medium confidence
        return 0.5

    def add_backchannel_word(self, word: str) -> None:
        """Add a word to the backchannel set."""
        self.backchannel_words.add(word.lower())

    def add_command_word(self, word: str) -> None:
        """Add a word to the command set."""
        self.command_words.add(word.lower())

    def remove_backchannel_word(self, word: str) -> None:
        """Remove a word from the backchannel set."""
        self.backchannel_words.discard(word.lower())

    def remove_command_word(self, word: str) -> None:
        """Remove a word from the command set."""
        self.command_words.discard(word.lower())
