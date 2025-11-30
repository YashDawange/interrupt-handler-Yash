# my_agent.py
import logging
import os
import asyncio
import time
import re
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from difflib import SequenceMatcher

from livekit.agents import Agent, AgentSession
from livekit.plugins import openai, elevenlabs, silero
from livekit.agents.metrics import LLMMetrics, STTMetrics, TTSMetrics, EOUMetrics

from interrupt_handler import BackchannelFilter, normalize_text

logger = logging.getLogger("dlai-agent")
logger.setLevel(logging.INFO)


# -------------------------
# Transcript Analysis
# -------------------------
@dataclass
class TranscriptAnalysis:
    is_backchannel: bool
    is_interrupt: bool
    is_mixed: bool
    reason: str
    confidence: float = 1.0


# -------------------------
# Controlled Agent Session
# -------------------------
class ControlledAgentSession(AgentSession):
    """
    Session with backchannel+interrupt filtering.
    """

    def __init__(self, *args, **kwargs):
        kwargs['min_interruption_words'] = kwargs.get('min_interruption_words', 3)
        kwargs['min_interruption_duration'] = kwargs.get('min_interruption_duration', 0.8)
        kwargs['false_interruption_timeout'] = kwargs.get('false_interruption_timeout', 1.5)
        kwargs['resume_false_interruption'] = kwargs.get('resume_false_interruption', True)

        super().__init__(*args, **kwargs)

        self._filter = BackchannelFilter()
        self._is_agent_speaking = False

        self.on("agent_started_speaking", self._on_agent_started_speaking)
        self.on("agent_stopped_speaking", self._on_agent_stopped_speaking)
        self.on("user_speech_committed", self._on_user_speech_committed)

        logger.info("Backchannel filtering enabled (hybrid model)")

    def _on_agent_started_speaking(self, event):
        self._is_agent_speaking = True

    def _on_agent_stopped_speaking(self, event):
        self._is_agent_speaking = False

    def _on_user_speech_committed(self, event):
        text = event.item.text_content or ""
        if not self._is_agent_speaking:
            logger.debug(f"User said while agent silent: {text}")
            return

        analysis = self._filter.analyze(text)

        if analysis.is_backchannel:
            logger.info(f"[BACKCHANNEL] {text} | {analysis.reason}")
        elif analysis.is_interrupt:
            logger.info(f"[INTERRUPT] {text} | {analysis.reason}")
        else:
            logger.info(f"[NEUTRAL] {text} | {analysis.reason}")


# -------------------------
# Controlled Agent
# -------------------------
class ControlledAgent(Agent):
    """Voice agent with metrics + backchannel filtering."""

    def __init__(self, *args, **kwargs):
        llm = openai.LLM(model=os.getenv("LLM_MODEL", "gpt-4o"))
        stt = openai.STT(model=os.getenv("STT_MODEL", "whisper-1"))
        tts = elevenlabs.TTS()
        vad = silero.VAD.load()

        super().__init__(
            instructions="You are a helpful assistant communicating via voice. Keep responses short.",
            stt=stt,
            llm=llm,
            tts=tts,
            vad=vad,
            *args,
            **kwargs
        )

        llm.on("metrics_collected", self._on_llm_metrics)
        stt.on("metrics_collected", self._on_stt_metrics)
        stt.on("eou_metrics_collected", self._on_eou_metrics)
        tts.on("metrics_collected", self._on_tts_metrics)

    def _on_llm_metrics(self, metrics: LLMMetrics):
        logger.info(f"[LLM] {metrics.prompt_tokens}→{metrics.completion_tokens}")

    def _on_stt_metrics(self, metrics: STTMetrics):
        logger.info(f"[STT] {metrics.duration:.2f}s")

    def _on_eou_metrics(self, metrics: EOUMetrics):
        logger.info(f"[EOU] delay={metrics.end_of_utterance_delay:.2f}s")

    def _on_tts_metrics(self, metrics: TTSMetrics):
        logger.info(f"[TTS] audio={metrics.audio_duration:.2f}s")
