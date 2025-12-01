from dataclasses import dataclass
import os
import re
import asyncio
import logging
from typing import Set, AsyncIterable, Any, Coroutine
from livekit.agents.voice import Agent, ModelSettings
from livekit.agents import stt
from livekit import rtc

logger = logging.getLogger(__name__)

def _parse_env_list(name: str, default: Set[str]) -> Set[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return {w.strip().lower() for w in raw.split(",") if w.strip()}

@dataclass
class BackchannelConfig:
    ignore_words: Set[str]
    interrupt_words: Set[str]
    interrupt_phrases: Set[str]

    @classmethod
    def from_env(cls) -> "BackchannelConfig":
        default_ignore = {"yeah", "ya", "yep", "ok", "okay", "k",
                          "hmm", "mm", "uh-huh", "right", "uh huh"}
        default_interrupt = {"stop", "wait", "no", "cancel", "hold"}
        default_phrases = {"wait a second", "hold on", "hang on"}

        return cls(
            ignore_words=_parse_env_list("BACKCHANNEL_IGNORE", default_ignore),
            interrupt_words=_parse_env_list("BACKCHANNEL_INTERRUPT", default_interrupt),
            interrupt_phrases=_parse_env_list("BACKCHANNEL_INTERRUPT_PHRASES", default_phrases),
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        return re.sub(r"[^a-zA-Z'\s]", " ", text.lower()).strip()

    def tokenize(self, text: str) -> list[str]:
        text = self.normalize_text(text)
        return [t for t in text.split() if t]

class BackchannelAwareAgent(Agent):
    def __init__(self, *args, backchannel_config: BackchannelConfig | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._backchannel_cfg = backchannel_config or BackchannelConfig.from_env()

    def stt_node(
        self, audio: AsyncIterable[rtc.AudioFrame], model_settings: ModelSettings
    ) -> AsyncIterable[stt.SpeechEvent]:
        
        async def _filtered_stream():
            # Get the original stream (handle coroutine if needed)
            original_result = super(BackchannelAwareAgent, self).stt_node(audio, model_settings)
            if asyncio.iscoroutine(original_result):
                original_stream = await original_result
            else:
                original_stream = original_result

            async for ev in original_stream:
                if ev.type in (stt.SpeechEventType.INTERIM_TRANSCRIPT, stt.SpeechEventType.FINAL_TRANSCRIPT):
                    text = ev.alternatives[0].text
                    # Check if agent is speaking
                    is_speaking = False
                    # Accessing internal _activity.session.agent_state
                    if self._activity and self._activity.session.agent_state == "speaking":
                        is_speaking = True
                    
                    if is_speaking:
                        normalized = self._backchannel_cfg.normalize_text(text)
                        tokens = self._backchannel_cfg.tokenize(normalized)
                        
                        should_interrupt = False
                        
                        # Logic:
                        # 1. Hard phrases -> Interrupt
                        if any(phrase in normalized for phrase in self._backchannel_cfg.interrupt_phrases):
                            should_interrupt = True
                            logger.debug(f"backchannel_decision: hard_interrupt (phrase) - '{text}'")
                        # 2. Hard words -> Interrupt
                        elif any(tok in self._backchannel_cfg.interrupt_words for tok in tokens):
                            should_interrupt = True
                            logger.debug(f"backchannel_decision: hard_interrupt (word) - '{text}'")
                        # 3. No tokens -> Don't interrupt yet (swallow)
                        elif not tokens:
                            should_interrupt = False
                            logger.debug(f"backchannel_decision: ignore (empty) - '{text}'")
                        # 4. All tokens in ignore list -> Ignore
                        elif all(tok in self._backchannel_cfg.ignore_words for tok in tokens):
                            should_interrupt = False
                            logger.debug(f"backchannel_decision: ignore (soft) - '{text}'")
                        # 5. Otherwise -> Interrupt
                        else:
                            should_interrupt = True
                            logger.debug(f"backchannel_decision: default_interrupt - '{text}'")
                            
                        if should_interrupt:
                            yield ev
                        else:
                            # Swallow event to prevent interruption
                            pass
                    else:
                        # Not speaking, pass everything
                        yield ev
                else:
                    # Other events (START_OF_SPEECH, END_OF_SPEECH, etc), pass them
                    yield ev

        return _filtered_stream()
