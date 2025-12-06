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
        This fixes the "agent stops too early" bug.
        """
        async def _tracking_tts_generator():
            tts_stream = super(IntelligentInterruptionAgent, self).tts_node(text, model_settings)
            
            self._is_speaking = True 
            logger.debug("Agent started speaking (State: True)")
            
            start_time = asyncio.get_event_loop().time()
            total_audio_duration = 0.0

            try:
                async for frame in tts_stream:
                    # 2. Calculate Audio Duration
                    if frame.samples_per_channel and frame.sample_rate:
                        duration = frame.samples_per_channel / frame.sample_rate
                        total_audio_duration += duration
                    yield frame
            except asyncio.CancelledError:
                self._is_speaking = False
                logger.debug("TTS Cancelled")
                raise
            finally:
                # 3. Calculate how much audio is left to play
                elapsed_gen_time = asyncio.get_event_loop().time() - start_time
                remaining_playback = total_audio_duration - elapsed_gen_time
                
                if remaining_playback < 0: 
                    remaining_playback = 0

                # 4. Add Safety Buffer (2.0s covers network lag)
                safety_buffer = 2.0
                total_wait = remaining_playback + safety_buffer

                if self._is_speaking and total_wait > 0:
                    logger.debug(f"TTS Gen done. Audio remaining: {remaining_playback:.2f}s. Waiting total {total_wait:.2f}s")
                    await asyncio.sleep(total_wait)
                
                self._is_speaking = False
                logger.debug("Agent finished speaking (State: False)")

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
                        logger.debug("START detected (agent speaking) - withholding")
                        speech_started = True
                        continue # Swallow
                    else:
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
                            logger.info(f"Real interrupt detected: '{clean_text}'")
                            # Yield the withheld START event now
                            yield stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH)
                            yield event
                            speech_started = False # Released
                        else:
                            # Still just backchannels ("yeah...", "um...")
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
                            # IGNORE
                            logger.info(f"Confirmed backchannel: '{clean_text}' - dropping")
                            speech_started = False
                            continue 
                        else:
                            #INTERRUPT
                            if speech_started:
                                yield stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH)
                                speech_started = False
                            logger.info(f"Confirmed interrupt: '{clean_text}'")
                            yield event
                    else:
                        #RESPOND
                        logger.info(f"→ Input (agent silent): '{clean_text}'")
                        yield event

                elif event.type == stt.SpeechEventType.END_OF_SPEECH:
                    if self._is_speaking and speech_started:
                        speech_started = False
                        continue 
                    yield event
                
                else:
                    yield event

        return _logic_layer_stt()
