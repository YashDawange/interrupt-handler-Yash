import logging
import asyncio
from typing import AsyncIterable
import string 

from livekit import rtc
from livekit.agents import stt, RunContext
from livekit.agents.voice import Agent as VoiceAgent, ModelSettings
from livekit.agents.llm import function_tool 

logger = logging.getLogger("intelligent-agent")

IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "uh-huh", "right", "aha", "mhm",
    "sure", "great", "yep", "yes", "alright", "got it", "i see"
}

PUNCTUATION_TABLE = str.maketrans('', '', string.punctuation.replace('-', ''))

class IntelligentInterruptionAgent(VoiceAgent):
    def __init__(self, *args, **kwargs):
        kwargs['allow_interruptions'] = True 
        super().__init__(*args, **kwargs)
        self._is_speaking = False
        self._playback_task = None

    async def on_enter(self):
        # Starts the conversation automatically
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."

    def tts_node(
        self, text: AsyncIterable[str], model_settings: ModelSettings
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Wrap TTS to track speaking state using EXACT AUDIO DURATION.
        Keeps _is_speaking=True until audio finishes playing, not just generating.
        """
        async def _tracking_tts_generator():
            tts_stream = super(IntelligentInterruptionAgent, self).tts_node(text, model_settings)
            
            # Mark as speaking immediately
            self._is_speaking = True 
            logger.debug("🔊 Agent started speaking (generation begins)")
            
            start_time = asyncio.get_event_loop().time()
            total_audio_duration = 0.0

            try:
                async for frame in tts_stream:
                    # Calculate audio duration as we generate
                    if frame.samples_per_channel and frame.sample_rate:
                        duration = frame.samples_per_channel / frame.sample_rate
                        total_audio_duration += duration
                    yield frame
            except asyncio.CancelledError:
                # Interrupted - cancel the playback task if it exists
                if self._playback_task and not self._playback_task.done():
                    self._playback_task.cancel()
                self._is_speaking = False
                logger.debug(" TTS Cancelled (interrupted during generation)")
                raise
            finally:
                # Generation is complete, but audio is still playing
                elapsed_gen_time = asyncio.get_event_loop().time() - start_time
                remaining_playback = total_audio_duration - elapsed_gen_time
                
                if remaining_playback < 0: 
                    remaining_playback = 0

                safety_buffer = 2.0
                total_wait = remaining_playback + safety_buffer

                logger.debug(f" TTS generation done. Audio remaining: {remaining_playback:.2f}s. Waiting {total_wait:.2f}s")
                
                if self._is_speaking and total_wait > 0:
                    async def _wait_for_playback():
                        try:
                            await asyncio.sleep(total_wait)
                            self._is_speaking = False
                            logger.debug(" Agent finished speaking (playback complete)")
                        except asyncio.CancelledError:
                            self._is_speaking = False
                            logger.debug(" Playback wait cancelled (interrupted during playback)")
                    
                    # Cancel any existing playback task
                    if self._playback_task and not self._playback_task.done():
                        self._playback_task.cancel()
                    
                    self._playback_task = asyncio.create_task(_wait_for_playback())
                else:
                    self._is_speaking = False
                    logger.debug("🔇 Agent finished speaking (no wait needed)")

        return _tracking_tts_generator()

    def stt_node(
        self, audio: AsyncIterable[rtc.AudioFrame], model_settings: ModelSettings
    ) -> AsyncIterable[stt.SpeechEvent]:
        """
        Intercept and intelligently filter STT events.
        Swallows START events for backchannels, re-injects them for real interruptions.
        """
        async def _logic_layer_stt():
            original_stream = super(IntelligentInterruptionAgent, self).stt_node(audio, model_settings)
            
            speech_started = False
            
            async for event in original_stream:
                
                if event.type == stt.SpeechEventType.START_OF_SPEECH:
                    if self._is_speaking:
                        logger.debug(" START detected (agent speaking) - withholding")
                        speech_started = True
                        continue # Swallow
                    else:
                        logger.debug(" START detected (agent silent) - passing through")
                        yield event

                elif event.type == stt.SpeechEventType.INTERIM_TRANSCRIPT:
                    if not event.alternatives: continue
                    
                    text_alt = event.alternatives[0].text
                    user_text = text_alt.strip().lower()
                    clean_text = user_text.translate(PUNCTUATION_TABLE).strip()
                    
                    if self._is_speaking and speech_started:
                        words = clean_text.split() if clean_text else []
                        # If we see a word that is NOT in ignore list, it's a REAL interruption
                        has_real_word = any(word not in IGNORE_WORDS for word in words)
                        
                        if has_real_word:
                            logger.info(f" Real interrupt detected: '{clean_text}'")
                            # Yield the withheld START event now
                            yield stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH)
                            yield event
                            speech_started = False # Released
                        else:
                            # Still just backchannels ("yeah...", "um...")
                            logger.debug(f" Interim backchannel: '{clean_text}' - withholding")
                            continue 
                    else:
                        yield event

                # 3. FINAL_TRANSCRIPT
                elif event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                    if not event.alternatives: continue
                    
                    text_alt = event.alternatives[0].text
                    user_text = text_alt.strip().lower()
                    clean_text = user_text.translate(PUNCTUATION_TABLE).strip()
                    if not clean_text: continue

                    words = clean_text.split()
                    all_backchannels = all(word in IGNORE_WORDS for word in words) if words else False
                    
                    if self._is_speaking:
                        if all_backchannels and speech_started:
                            # IGNORE - confirmed backchannel
                            logger.info(f" Confirmed backchannel: '{clean_text}' - dropping")
                            speech_started = False
                            continue 
                        else:
                            # INTERRUPT - real interruption
                            if speech_started:
                                yield stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH)
                                speech_started = False
                            logger.info(f" Confirmed interrupt: '{clean_text}'")
                            yield event
                    else:
                        # RESPOND - agent is silent
                        logger.info(f"→ Input (agent silent): '{clean_text}'")
                        yield event

                elif event.type == stt.SpeechEventType.END_OF_SPEECH:
                    if self._is_speaking and speech_started:
                        # Drop the END event for backchannels
                        logger.debug(" END (backchannel) - dropping")
                        speech_started = False
                        continue 
                    yield event
                
                else:
                    yield event

        return _logic_layer_stt()
