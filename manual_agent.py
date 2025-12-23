import asyncio
import logging
import os
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli, stt
from livekit.plugins import deepgram, silero
from openai import AsyncOpenAI

load_dotenv()
logger = logging.getLogger("manual-agent")

# --- CONFIGURATION ---
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "mhmm", "uh-huh", "right", "sure", "yes", "yep", "correct", "i see", "go on"
}

STOP_WORDS = {
    "stop", "wait", "hold on", "cancel", "shut up", "pause", "no", "hey", "quit", "silence", "enough"
}

def clean_text(text: str) -> str:
    return "".join(c for c in text if c.isalnum() or c.isspace()).lower().strip()

class ManualOrchestrator:
    def __init__(self, ctx: JobContext):
        self.ctx = ctx
        self.room = ctx.room
        self.vad = silero.VAD.load()
        self.stt = deepgram.STT(model="nova-2-general", smart_format=True, interim_results=True)
        self.client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"))
        self.tts = deepgram.TTS() 

        self.chat_history = [
            {"role": "system", "content": "You are a helpful assistant. If asked for a story, keep it engaging."}
        ]
        
        self.is_speaking = False
        self.audio_source = None 
        self.interrupt_flag = asyncio.Event()
        self.current_response_task = None

    async def start(self):
        self.audio_source = rtc.AudioSource(24000, 1)
        track = rtc.LocalAudioTrack.create_audio_track("agent-voice", self.audio_source)
        await self.room.local_participant.publish_track(track)

        participant = await self.ctx.wait_for_participant()
        logger.info(f"User connected: {participant.identity}")
        
        mic_publication = None
        while not mic_publication:
            for pub in participant.track_publications.values():
                if pub.source == rtc.TrackSource.SOURCE_MICROPHONE:
                    mic_publication = pub
                    break
            if not mic_publication: await asyncio.sleep(0.5)
        while not mic_publication.track: await asyncio.sleep(0.1)

        audio_stream = rtc.AudioStream(mic_publication.track)
        logger.info("Audio stream connected! Ready.")
        
        asyncio.create_task(self.listen_loop(audio_stream))
        
        # AUTO-START
        logger.info("🤖 Starting story in 1 second...")
        await asyncio.sleep(1.0)
        self.current_response_task = asyncio.create_task(
            self.generate_response("Tell me a long story about the history of the universe.")
        )

    async def listen_loop(self, audio_stream):
        vad_stream = self.vad.stream()
        stt_stream = self.stt.stream()
        asyncio.create_task(self.handle_stt_events(stt_stream))

        async for event in audio_stream:
            stt_stream.push_frame(event.frame)
            vad_stream.push_frame(event.frame)

    async def handle_stt_events(self, stt_stream):
        async for event in stt_stream:
            is_final = False
            if hasattr(event, 'type'):
                if "FINAL_TRANSCRIPT" in str(event.type): is_final = True
            elif hasattr(event, 'is_final'):
                is_final = event.is_final
            
            if not event.alternatives: continue
            text = event.alternatives[0].text.strip()
            if not text: continue
            
            clean_input = clean_text(text)

            # --- INTERRUPT LOGIC ---
            if self.is_speaking:
                if clean_input in IGNORE_WORDS:
                    logger.info(f"🛡️ [SOFT INTERRUPT] Ignored: '{text}'")
                    continue 
                else:
                    logger.info(f"🛑 [HARD INTERRUPT] Stopping for: '{text}'")
                    await self.stop_speaking()
            
            if is_final:
                logger.info(f"👂 HEARD: '{text}'")
                if not self.is_speaking:
                    if self.current_response_task:
                        self.current_response_task.cancel()
                    self.current_response_task = asyncio.create_task(self.generate_response(text))

    async def stop_speaking(self):
        if self.is_speaking:
            self.interrupt_flag.set() 
            self.is_speaking = False
            
            # Cancel the task to stop generation immediately
            if self.current_response_task:
                self.current_response_task.cancel()

    async def generate_response(self, input_text):
        self.chat_history.append({"role": "user", "content": input_text})
        self.is_speaking = True
        self.interrupt_flag.clear()

        try:
            stream = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=self.chat_history,
                stream=True
            )
        except Exception as e:
            logger.error(f"❌ LLM Error: {e}")
            self.is_speaking = False
            return

        full_response = ""
        current_sentence = ""
        
        try:
            async for chunk in stream:
                if self.interrupt_flag.is_set(): 
                    logger.info("✋ Generation halted by interrupt.")
                    break
                
                content = chunk.choices[0].delta.content
                if not content: continue
                
                full_response += content
                current_sentence += content
                
                if content in [".", "?", "!", "\n", ",", ":", ";"]:
                    if current_sentence.strip():
                        await self.synthesize_and_play(current_sentence)
                    current_sentence = ""

            if current_sentence.strip() and not self.interrupt_flag.is_set():
                 await self.synthesize_and_play(current_sentence)

        except Exception as e:
            pass 

        self.chat_history.append({"role": "assistant", "content": full_response})
        
        # Buffer
        if not self.interrupt_flag.is_set():
            await asyncio.sleep(2.0)
        
        self.is_speaking = False
        logger.info("✅ Agent finished. Waiting for user input.")

    async def synthesize_and_play(self, text):
        if self.interrupt_flag.is_set(): return
        if not text.strip(): return
        
        logger.info(f"🤖 AGENT: '{text.strip()}'")
        try:
            audio_stream = self.tts.synthesize(text)
            async for audio_event in audio_stream:
                if self.interrupt_flag.is_set(): 
                    break # Stop capturing new frames
                await self.audio_source.capture_frame(audio_event.frame)
        except Exception as e:
            logger.error(f"TTS Error: {e}")

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    agent = ManualOrchestrator(ctx)
    await agent.start()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))