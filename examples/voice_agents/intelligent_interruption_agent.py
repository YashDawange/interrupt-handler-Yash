import logging
import asyncio
import time
from typing import Sequence
from dotenv import load_dotenv
import os
import re
import json
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
    room_io,
    llm,
    stt,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import AgentActivity to subclass it
from livekit.agents.voice.agent_activity import AgentActivity, _EndOfTurnInfo
from livekit.agents.voice import agent_session

logger = logging.getLogger("intelligent-interruption-agent")

load_dotenv()

# --- Intelligent Interruption Logic ---

# Load ignore list from ENV or default to strict list

default_ignore = ["yeah", "ok", "hmm", "right", "uh-huh", "uh", "um"]

env_ignore = os.getenv("INTERRUPTION_IGNORE_WORDS")
IGNORE_WORDS_SET = set(json.loads(env_ignore)) if env_ignore else set(default_ignore)

class IntelligentAgentActivity(AgentActivity):
    def _interrupt_by_audio_activity(self) -> None:
        opt = self._session.options
        
        if isinstance(self.llm, llm.RealtimeModel) and self.llm.capabilities.turn_detection:
            return

        
        if (self.stt is not None and self._audio_recognition is not None):
            text = self._audio_recognition.current_transcript
            
            
            if not text or not text.strip():
                return

            # CLEANING: Remove punctuation to handle "Yeah!" or "Ok..."
            clean_text = re.sub(r'[^\w\s]', '', text).lower()
            words = clean_text.split()

            if not words:
                return

            # LOGIC: Check if ALL words are in the ignore set
            if all(w in IGNORE_WORDS_SET for w in words):
                return

            
            if opt.min_interruption_words > 0:
                if len(words) < opt.min_interruption_words:
                    return

        super()._interrupt_by_audio_activity()

    def on_end_of_turn(self, info: _EndOfTurnInfo) -> bool:
        
        
        if self._scheduling_paused:
            self._cancel_preemptive_generation()
            logger.warning("skipping user input, speech scheduling is paused", extra={"user_input": info.new_transcript})
            if self._session._closing:
                user_message = llm.ChatMessage(
                    role="user",
                    content=[info.new_transcript],
                    transcript_confidence=info.transcript_confidence,
                )
                self._agent._chat_ctx.items.append(user_message)
                self._session._conversation_item_added(user_message)
            return True

       
        if (
            self.stt is not None
            and self._turn_detection != "manual"
            and self._current_speech is not None
            and self._current_speech.allow_interruptions
            and not self._current_speech.interrupted
        ):
            
            clean_text = re.sub(r'[^\w\s]', '', info.new_transcript).lower()
            words = clean_text.split()
            
            # If the entire turn was just "yeah", cancel the generation so the Agent doesn't reply.
            if words and all(w in IGNORE_WORDS_SET for w in words):
                self._cancel_preemptive_generation()
                return False

            if (
                self._session.options.min_interruption_words > 0
                and len(words) < self._session.options.min_interruption_words
            ):
                self._cancel_preemptive_generation()
                return False

        old_task = self._user_turn_completed_atask
        self._user_turn_completed_atask = self._create_speech_task(
            self._user_turn_completed_task(old_task, info),
            name="AgentActivity._user_turn_completed_task",
        )
        return True

agent_session.AgentActivity = IntelligentAgentActivity

# --- End Intelligent Interruption Logic ---


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Nirdesh. You are a helpful and knowledgeable history expert."
            "You love telling long, detailed stories about historical events."
            "When asked about a topic, provide a comprehensive answer with interesting facts."
            "You are curious and friendly, and have a sense of humor."
            "You will speak English to the user.",
        )

    async def on_enter(self):
        self.session.generate_reply()


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    session = AgentSession(
        
        stt="deepgram/nova-3",
        
        llm="openai/gpt-4.1-mini",

        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",

        
        

        

        
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        
        preemptive_generation=True,
        
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        min_interruption_words=1, # Ensure we wait for at least 1 word to check against ignore list
    )


    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")


    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
