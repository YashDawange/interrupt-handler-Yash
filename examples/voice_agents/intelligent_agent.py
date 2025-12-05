import logging
import asyncio
from typing import AsyncIterable, Any

from livekit import rtc
from livekit.agents import stt, tts
from livekit.agents.voice import Agent as VoiceAgent, ModelSettings

logger = logging.getLogger("intelligent-agent")

# [cite_start]1. Configurable Ignore List [cite: 37]
# Added "great", "sure" to help with your specific test case
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "uh-huh", "right", "aha", "mhm",
    "sure", "great", "yep", "yes"
}

class IntelligentInterruptionAgent(VoiceAgent):
    def __init__(self, *args, **kwargs):
        # Allow interruptions at the system level so we can control them manually
        kwargs['allow_interruptions'] = True 
        super().__init__(*args, **kwargs)
        self._is_speaking = False

    def tts_node(
        self, text: AsyncIterable[str], model_settings: ModelSettings
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Wrap TTS to track speaking state with buffer delay.
        """
        async def _tracking_tts_generator():
            tts_stream = super(IntelligentInterruptionAgent, self).tts_node(text, model_settings)
            try:
                async for frame in tts_stream:
                    self._is_speaking = True 
                    yield frame
            except asyncio.CancelledError:
                self._is_speaking = False
                raise
            finally:
                # [cite_start]Buffer Delay: Keep state 'speaking' while audio plays out [cite: 49]
                if self._is_speaking:
                    await asyncio.sleep(1.5)
                self._is_speaking = False

        return _tracking_tts_generator()

    def stt_node(
        self, audio: AsyncIterable[rtc.AudioFrame], model_settings: ModelSettings
    ) -> AsyncIterable[stt.SpeechEvent]:
        """
        Logic Layer: Filters ALL events (Start, Interim, Final) based on context.
        """
        async def _logic_layer_stt():
            original_stream = super(IntelligentInterruptionAgent, self).stt_node(audio, model_settings)
            
            async for event in original_stream:
                
                # 1. Handle "Start of Speech" (VAD)
                # We swallow this so the parent agent doesn't stop audio immediately.
                if event.type == stt.SpeechEventType.START_OF_SPEECH:
                    if self._is_speaking:
                        # Log it but DON'T yield it. Keep the agent in the dark.
                        logger.debug("Swallowing START_OF_SPEECH while speaking")
                        continue 
                    else:
                        yield event

                # 2. Handle Text (Interim & Final)
                elif event.type in [stt.SpeechEventType.FINAL_TRANSCRIPT, stt.SpeechEventType.INTERIM_TRANSCRIPT]:
                    
                    # Clean the text
                    text_alt = event.alternatives[0].text
                    user_text = text_alt.strip().lower()
                    # Remove punctuation for comparison
                    clean_text = ''.join(char for char in user_text if char.isalnum() or char in [' ', '-'])
                    
                    if not clean_text:
                        continue

                    # Check against list
                    # We look for EXACT match or presence in list
                    # e.g. "Yeah..." -> "yeah" -> Match
                    is_ignore_word = clean_text in IGNORE_WORDS
                    
                    if self._is_speaking:
                        if is_ignore_word:
                            # SCENARIO 1: IGNORE
                            # We drop BOTH interim and final results for ignore words.
                            # This ensures the agent never sees them.
                            if event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                                logger.info(f"Ignoring backchannel '{clean_text}'")
                            continue 
                        
                        else:
                            # SCENARIO 3/4: INTERRUPT
                            # If it's NOT an ignore word, we interrupt.
                            # For interim results, we might wait for confidence, but for this assignment,
                            # stopping fast on "Stop" is better.
                            
                            # Only log on Final to avoid spam
                            if event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                                logger.info(f"Valid interruption '{clean_text}'. Stopping.")
                            
                            # Manually trigger the interruption handle
                            if self._activity:
                                await self._activity.interrupt()
                            
                            yield event 
                            
                    else:
                        # SCENARIO 2: RESPOND (Agent Silent)
                        yield event
                
                else:
                    # Pass through other events (like END_OF_SPEECH)
                    yield event

        return _logic_layer_stt()