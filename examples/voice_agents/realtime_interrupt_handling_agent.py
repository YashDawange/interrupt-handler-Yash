import logging
from dataclasses import dataclass, field
from enum import Enum
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
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class SpeechIntent(Enum):
    BACKCHANNEL = "backchannel"
    INTERRUPTION = "interruption"
    UTTERANCE = "utterance"


@dataclass
class TranscriptRecord:
    content: str
    timestamp: datetime
    is_final: bool


@dataclass
class InterruptDetectionConfig:
    acknowledgment_tokens: Set[str] = field(default_factory=lambda: {
        "yeah", "yep", "ok", "okay", "right", "sure", "cool", "nice", "interesting"
    })

    acknowledgment_phrases: Set[str] = field(default_factory=lambda: {
        "got it",
        "makes sense",
        "understood",
        "i see",
        "sounds good",
        "all right",
    })

    filler_phrases: Set[str] = field(default_factory=lambda: {
        "uh huh", "mm hmm", "hmm", "uh-huh"
    })

    interrupt_keywords: Set[str] = field(default_factory=lambda: {
        "wait",
        "stop",
        "pause",
        "hold on",
        "actually",
        "no no",
        "wait a second",
    })


class InterruptStateController:
    def __init__(self, config: InterruptDetectionConfig):
        self.config = config
        self.history: deque[TranscriptRecord] = deque(maxlen=100)
        self.agent_speaking = False

    def _normalize(self, text: str) -> str:
        return text.lower().replace(",", "").replace(".", "").strip()

    def classify_intent(self, text: str) -> SpeechIntent:
        normalized = self._normalize(text)

        for keyword in self.config.interrupt_keywords:
            if keyword in normalized:
                return SpeechIntent.INTERRUPTION

        if normalized in self.config.acknowledgment_tokens:
            return SpeechIntent.BACKCHANNEL

        if normalized in self.config.acknowledgment_phrases:
            return SpeechIntent.BACKCHANNEL

        if normalized in self.config.filler_phrases:
            return SpeechIntent.BACKCHANNEL

        tokens = normalized.split()
        if len(tokens) <= 2 and all(len(token) <= 5 for token in tokens):
            return SpeechIntent.BACKCHANNEL

        return SpeechIntent.UTTERANCE

    async def should_drop_transcript(self, text: str, is_final: bool) -> bool:
        self.history.append(
            TranscriptRecord(text, datetime.now(), is_final)
        )

        if not self.agent_speaking:
            return False

        intent = self.classify_intent(text)

        if intent == SpeechIntent.INTERRUPTION:
            return False

        if intent == SpeechIntent.BACKCHANNEL:
            return True

        return False


class ConversationalVoiceAgent(Agent):
    def __init__(self, controller: InterruptStateController):
        super().__init__(
            instructions=(
                "You are a calm, conversational voice assistant.\n\n"
                "Turn-taking behavior:\n"
                "- Ignore acknowledgements such as 'yeah', 'okay', or 'right' "
                "while you are speaking.\n"
                "- If the user says 'wait', 'stop', 'hold on', or begins a new "
                "sentence, immediately stop speaking and listen.\n"
                "- Never respond to acknowledgements.\n"
                "- Respond only when the user clearly wants the turn.\n\n"
                "Maintain a natural, human-like conversational flow."
            )
        )
        self.controller = controller

    async def stt_node(
        self,
        audio: AsyncIterable[rtc.AudioFrame],
        model_settings: ModelSettings,
    ) -> Optional[AsyncIterable[stt.SpeechEvent]]:

        upstream = Agent.default.stt_node(self, audio, model_settings)
        if upstream is None:
            return None

        async def stream():
            async for event in upstream:
                if event.type in (
                    stt.SpeechEventType.INTERIM_TRANSCRIPT,
                    stt.SpeechEventType.FINAL_TRANSCRIPT,
                ):
                    if event.alternatives:
                        transcript = event.alternatives[0].text
                        suppress = await self.controller.should_drop_transcript(
                            transcript,
                            event.type == stt.SpeechEventType.FINAL_TRANSCRIPT,
                        )
                        if suppress:
                            logger.info(f"Dropped backchannel: {transcript}")
                            continue
                yield event

        return stream()


turn_config = InterruptDetectionConfig()
turn_controller = InterruptStateController(turn_config)
server = AgentServer()


@server.rtc_session()
async def run_agent(ctx: agents.JobContext):
    agent = ConversationalVoiceAgent(turn_controller)

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=silero.VAD.load(
            min_speech_duration=0.4,
            min_silence_duration=0.4,
        ),
        turn_detection=MultilingualModel(),
        min_endpointing_delay=0.8,
        allow_interruptions=True,
    )

    @session.on("agent_state_changed")
    def handle_agent_state(event):
        turn_controller.agent_speaking = event.new_state == "speaking"

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC()
            ),
        ),
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
