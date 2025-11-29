from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, google, silero, cartesia

from settings import InterruptionSettings
from logger import EventLogger
from transcript_buffer import TranscriptBuffer
from classifier import InputClassifier
from analyzer import ConversationAnalyzer
from utils import require_env, extract_user_utterance


async def entrypoint(ctx: JobContext):
    """Main async entrypoint that initializes the agent and handles user interactions."""
    await ctx.connect()

    config = InterruptionSettings.load_from_environment()
    logger = EventLogger()
    transcript_buf = TranscriptBuffer(
        max_entries=config.buffer_capacity,
        duplicate_window_seconds=config.duplicate_window_seconds,
    )
    classifier = InputClassifier()
    analyzer = ConversationAnalyzer(config, logger)

    logger.capture_lifecycle_event("Services initialized")

    llm = google.LLM(model=os.getenv("GOOGLE_LLM_MODEL", "gemini-2.5-flash"))

    agent = Agent(
        instructions=(
            "You are a friendly, natural voice assistant. Respond conversationally, "
            "keep answers concise, maintain context, and speak at a natural pace. "
            "Pause between thoughts to seem human-like. Handle interruptions gracefully."
        ),
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model=os.getenv("DEEPGRAM_MODEL", "nova-3")),
        llm=llm,
        tts=cartesia.TTS(),
        allow_interruptions=True,
        turn_detection="vad",
        discard_audio_if_uninterruptible=False,
    )

    await session.start(agent=agent, room=ctx.room)
    logger.capture_lifecycle_event("LiveKit session started")

    agent_state = "initializing"
    agent_is_speaking = False

    last_interrupt_time: Optional[datetime] = None
    is_processing_reply = False

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        """Callback: track when the agent starts/stops speaking."""
        nonlocal agent_state, agent_is_speaking, is_processing_reply
        agent_state = getattr(ev, "new_state", agent_state)
        agent_is_speaking = (agent_state == "speaking")
        logger.capture_action("AGENT_STATE", agent_state)

        if agent_state == "listening":
            is_processing_reply = False

    @session.on("conversation_item_added")
    def _on_item_added(ev):
        """Callback: detect when assistant output is finalized."""
        nonlocal is_processing_reply
        try:
            item = getattr(ev, "item", None)
            role = getattr(item, "role", None)
            if role == "assistant":
                is_processing_reply = False
                logger.capture_action("ASSISTANT_COMMITTED")
        except Exception:
            pass

    @session.on("user_input_transcribed")
    def _on_user_transcribed(event):
        """Callback: handle user transcription events asynchronously."""
        asyncio.create_task(_process(event))

    async def _process(event):
        """Core logic for classifying, analyzing, and responding to user input."""
        nonlocal last_interrupt_time, is_processing_reply, agent_is_speaking

        try:
            utterance = extract_user_utterance(event)
            if not utterance:
                return

            is_final = bool(getattr(event, "is_final", True))

            if transcript_buf.contains_recent(utterance):
                return
            transcript_buf.add_entry(utterance)

            logger.capture_user_input(utterance, is_final, agent_is_speaking)

            now = datetime.now()
            if last_interrupt_time:
                elapsed_ms = (now - last_interrupt_time).total_seconds() * 1000.0
                if elapsed_ms < config.cooldown_milliseconds:
                    logger.capture_handling_decision(
                        "COOLDOWN",
                        f"Ignored ({elapsed_ms:.0f}ms < {config.cooldown_milliseconds:.0f}ms)",
                    )
                    return

            input_type = classifier.categorize_input(utterance)
            logger.capture_classification(utterance, input_type)

            strategy = analyzer.determine_handling_strategy(
                utterance=utterance,
                classification=input_type,
                agent_is_speaking=agent_is_speaking,
                is_final=is_final,
            )

            if strategy == "IGNORE":
                return

            if strategy == "INTERRUPT":
                logger.capture_action("INTERRUPT", "force=True")
                last_interrupt_time = now
                await session.interrupt(force=True)
                is_processing_reply = False
                return

            if strategy == "INTERRUPT_AND_RESPOND":
                logger.capture_action("INTERRUPT_AND_RESPOND")
                last_interrupt_time = now
                await session.interrupt(force=True)
                await asyncio.sleep(config.interrupt_settle_delay_seconds)

                if not is_processing_reply:
                    is_processing_reply = True
                    session.generate_reply(user_input=utterance, allow_interruptions=False)
                return

            if strategy == "RESPOND":
                if not is_processing_reply:
                    logger.capture_action("RESPOND")
                    is_processing_reply = True
                    session.generate_reply(user_input=utterance, allow_interruptions=False)
                return

            return

        except Exception as e:
            logger.capture_error("process failed", e)

    logger.capture_lifecycle_event("Agent greeting")
    session.say("Hello! How can I help you today?", allow_interruptions=False)


def main():
    """Load environment variables and start the LiveKit worker."""
    load_dotenv()
    require_env(
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "DEEPGRAM_API_KEY",
        "GOOGLE_API_KEY",
        "CARTESIA_API_KEY",
    )
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
