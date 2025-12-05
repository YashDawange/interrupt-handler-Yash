"""
Intelligent Interruption Handler for LiveKit Agents

Purpose:
--------
This system enables smarter handling of user interruptions during agent speech.
It allows harmless backchannel words (like “yeah”, “ok”, “hmm”) to be ignored,
while still recognizing meaningful interruptions such as “wait” or “stop”.

Features:
---------
- Tracks when the agent is speaking or silent
- Identifies filler/backchannel words and ignores them while speaking
- Detects actual interruption intents via keywords
- Automatically resumes speech when the interruption was only filler
"""

import asyncio
import logging
import os
import re
from typing import Set

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit import rtc
from livekit.plugins import silero


# -----------------------------------------
# Logging Setup
# -----------------------------------------

logger = logging.getLogger("intelligent-interruption-agent")
logger.setLevel(logging.INFO)

# Save all logs, including framework logs
log_file = os.path.join(os.path.dirname(__file__), "../../LOGS_SUBMISSION.log")
file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-25s %(message)s",
    datefmt="%H:%M:%S"
))
logger.addHandler(file_handler)

# Console output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    "%(asctime)s.%(msecs)03d %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S"
))
logger.addHandler(console_handler)

# Capture all logs (root logger)
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)

load_dotenv()        

# -----------------------------------------
# Filler & Interruption Word Sets
# -----------------------------------------

DEFAULT_FILLER_WORDS = {
    "yeah", "yep", "yes", "yup", "yea",
    "ok", "okay", "k",
    "hmm", "hm", "mm", "mmm", "mhm", "mm-hmm", "uh-huh",
    "right", "sure", "alright", "got it",
    "i see", "i understand", "understood",
    "aha", "oh", "ah",
    "cool", "nice", "great",
    "continue", "go on", "go ahead"
}

INTERRUPTION_KEYWORDS = {
    "wait", "stop", "pause", "hold", "hold on", "no",
    "but", "actually", "however",
    "question", "what", "why", "how", "when", "where", "who"
}

# -----------------------------------------
# Interruption Handler Class
# -----------------------------------------

class IntelligentInterruptionHandler:
    """
    Implements intelligent interruption rules using STT transcripts and agent state.
    """

    def __init__(
        self,
        session: AgentSession,
        filler_words: Set[str] = None,
        interruption_keywords: Set[str] = None,
        min_words_for_interruption: int = 2,
    ):
        self.session = session
        self.filler_words = filler_words or DEFAULT_FILLER_WORDS
        self.interruption_keywords = interruption_keywords or INTERRUPTION_KEYWORDS
        self.min_words_for_interruption = min_words_for_interruption

        self._agent_was_speaking = False
        self._last_transcript = ""
        self._pending_resume_task = None

        # Connect to session events
        self.session.on("agent_state_changed", self._on_agent_state_changed)
        self.session.on("user_input_transcribed", self._on_user_input)

        logger.info(
            f"Interruption handler initialized with "
            f"{len(self.filler_words)} fillers and "
            f"{len(self.interruption_keywords)} interrupt triggers."
        )

    # -----------------------------
    # Utility Helpers
    # -----------------------------

    def _normalize(self, text: str) -> str:
        """Lowercase + remove punctuation + collapse spaces."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        return re.sub(r"\s+", " ", text)

    def _is_filler_only(self, text: str) -> bool:
        """True if all words are filler words."""
        if not text:
            return True

        words = self._normalize(text).split()
        return all(word in self.filler_words for word in words)

    def _contains_interrupt_keyword(self, text: str) -> bool:
        """True if any keyword or phrase appears in text."""
        normalized = self._normalize(text)
        words = normalized.split()

        if any(word in self.interruption_keywords for word in words):
            return True

        return any(phrase in normalized for phrase in self.interruption_keywords if " " in phrase)

    # -----------------------------
    # Decision Logic
    # -----------------------------

    def _should_ignore(self, text: str, agent_speaking: bool) -> bool:
        """
        Determines whether to ignore an interruption:
        - If agent not speaking: never ignore
        - If text contains interruption triggers: allow interruption
        - If only filler: ignore
        """
        logger.info(f"Checking interruption: agent_speaking={agent_speaking}, text='{text}'")

        if not agent_speaking:
            return False

        if self._contains_interrupt_keyword(text):
            return False

        if self._is_filler_only(text):
            return True

        return False

    # -----------------------------
    # Event Handlers
    # -----------------------------

    def _on_agent_state_changed(self, event):
        logger.info(f"Agent state: {event.old_state} -> {event.new_state}")

        if event.new_state == "speaking":
            self._agent_was_speaking = True
        elif event.old_state == "speaking":
            self._agent_was_speaking = False

    def _on_user_input(self, event):
        text = getattr(event, "transcript", "") or ""
        is_final = getattr(event, "is_final", False)

        logger.info(
            f"User transcript ({'final' if is_final else 'interim'}): '{text}', "
            f"agent_speaking={self._agent_was_speaking}"
        )

        self._last_transcript = text

        if not text.strip():
            return

        ignore = self._should_ignore(text, self._agent_was_speaking)

        if ignore:
            logger.info("Ignoring filler interruption. Resuming speech.")
            if self._pending_resume_task and not self._pending_resume_task.done():
                self._pending_resume_task.cancel()
            self._pending_resume_task = asyncio.create_task(self._resume_speech())
        else:
            logger.info("Valid interruption detected.")

    async def _resume_speech(self):
        """Force-resumes agent speech after a filler interruption."""
        try:
            await asyncio.sleep(0.05)

            audio = self.session.output.audio
            if audio and audio.can_pause:
                self.session._update_agent_state("speaking")
                audio.resume()
                logger.info("Speech resumed successfully.")
            else:
                logger.warning("Cannot resume speech: audio output unsupported.")

        except Exception as e:
            logger.error(f"Resume speech failed: {e}", exc_info=True)


# -----------------------------------------
# Main Agent Class
# -----------------------------------------

class IntelligentInterruptionAgent(Agent):

    def __init__(self):
        super().__init__(
            instructions=(
                "Your name is Alex, a helpful voice assistant. "
                "Speak in clear, detailed paragraphs. "
                "Avoid emojis or special formatting. "
                "Respond in a friendly, conversational tone."
            )
        )
        self.interruption_handler = None

    async def on_enter(self):
        self.interruption_handler = IntelligentInterruptionHandler(
            session=self.session,
            filler_words=DEFAULT_FILLER_WORDS,
            interruption_keywords=INTERRUPTION_KEYWORDS,
        )

        self.session.generate_reply(
            instructions=(
                "Give a warm greeting and introduce the intelligent interruption demo. "
                "Explain that filler words like 'yeah' or 'hmm' won't interrupt you, "
                "but words like 'wait' or 'stop' will."
            )
        )

    # Tools for demonstration
    @function_tool
    async def explain_topic(self, context: RunContext, topic: str):
        return (
            f"I will now explain {topic} in detail. "
            "The explanation will be long to demonstrate interruption behavior."
        )

    @function_tool
    async def count_to_number(self, context: RunContext, number: int):
        seq = ", ".join(str(i) for i in range(1, min(number + 1, 51)))
        return f"Counting: {seq}"


# -----------------------------------------
# Server Setup & Entry Point
# -----------------------------------------

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info(f"Starting intelligent interruption agent in room {ctx.room.name}")

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=ctx.proc.userdata["vad"],
        allow_interruptions=True,
        min_interruption_duration=0.3,
        resume_false_interruption=True,
        false_interruption_timeout=0.2,
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage summary: {usage_collector.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=IntelligentInterruptionAgent(),
        room=ctx.room,
    )

    logger.info("Agent session started successfully.")


if __name__ == "__main__":
    cli.run_app(server)