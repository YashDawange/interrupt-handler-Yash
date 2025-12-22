import logging
from dataclasses import dataclass, field
from enum import Enum
import os
from typing import Set, AsyncIterable, Optional
from collections import deque
from datetime import datetime

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    Agent,
    room_io,
    stt,
)
from livekit.agents.voice import ModelSettings
from livekit.plugins import noise_cancellation, silero, google
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(".env.local")

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class InterruptType(Enum):
    BACKCHANNEL = "backchannel"
    COMMAND = "command"
    NORMAL = "normal"


@dataclass
class TranscriptEvent:
    text: str
    timestamp: datetime
    is_final: bool


@dataclass
class InterruptionConfig:
    backchannel_words: Set[str] = field(default_factory=lambda: {
        "yeah", "ok", "okay", "hmm", "uh-huh"
    })

    interrupt_words: Set[str] = field(default_factory=lambda: {
        "wait", "stop", "no", "pause", "hold on"
    })


class InterruptionManager:
    def __init__(self, config: InterruptionConfig):
        self.config = config
        self.transcript_buffer: deque[TranscriptEvent] = deque(maxlen=100)
        self.is_agent_speaking = False

    def _classify(self, text: str) -> InterruptType:
        clean_text = text.lower().replace(",", " ").replace(".", " ").strip()
        words = {w for w in clean_text.split() if w}

        if words & self.config.interrupt_words:
            return InterruptType.COMMAND

        if words and words <= self.config.backchannel_words:
            return InterruptType.BACKCHANNEL

        return InterruptType.NORMAL

    async def should_suppress(self, text: str, is_final: bool) -> bool:
        self.transcript_buffer.append(
            TranscriptEvent(text, datetime.now(), is_final)
        )

        if not is_final:
            return False

        if not self.is_agent_speaking:
            return False

        interrupt_type = self._classify(text)

        if interrupt_type == InterruptType.BACKCHANNEL:
            return True

        return False


class InterruptAwareAssistant(Agent):
    def __init__(self, manager: InterruptionManager):
        super().__init__(
            instructions=(
                "You are a helpful voice assistant. "
                "When users say acknowledgments like 'yeah' or 'okay' while "
                "you are speaking, continue naturally without reacting."
            )
        )
        self.manager = manager

    async def stt_node(
        self,
        audio: AsyncIterable[rtc.AudioFrame],
        model_settings: ModelSettings,
    ) -> Optional[AsyncIterable[stt.SpeechEvent]]:

        stream = Agent.default.stt_node(self, audio, model_settings)
        if stream is None:
            return None

        async def filtered():
            async for event in stream:
                if event.type in (
                    stt.SpeechEventType.INTERIM_TRANSCRIPT,
                    stt.SpeechEventType.FINAL_TRANSCRIPT,
                ):
                    if event.alternatives:
                        text = event.alternatives[0].text
                        suppress = await self.manager.should_suppress(
                            text,
                            event.type == stt.SpeechEventType.FINAL_TRANSCRIPT,
                        )
                        if suppress:
                            logger.info(f"Suppressing backchannel: '{text}'")
                            continue
                yield event

        return filtered()


config = InterruptionConfig()
interrupt_manager = InterruptionManager(config)

server = AgentServer()


@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    assistant = InterruptAwareAssistant(interrupt_manager)

    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm=google.LLM(
            model="gemini-2.5-flash",
            api_key=os.getenv("GOOGLE_API_KEY"),
        ),
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(
            min_speech_duration=0.5,
            min_silence_duration=0.8,
        ),
        turn_detection=MultilingualModel(),
        min_endpointing_delay=1.0,
        allow_interruptions=True,
    )
    
    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        if ev.new_state == "speaking":
            interrupt_manager.is_agent_speaking = True
        elif ev.new_state in ("listening", "thinking", "initializing"):
            interrupt_manager.is_agent_speaking = False

    await session.start(
        room=ctx.room,
        agent=assistant,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda p: (
                    noise_cancellation.BVCTelephony()
                    if p.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)