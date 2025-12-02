import logging
import ssl
import asyncio
from dotenv import load_dotenv
load_dotenv()
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, silero

# Fix SSL certificate verification on macOS
ssl._create_default_https_context = ssl._create_unverified_context

IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "aha", "uh-huh", "right", "yep", "sure", "i see", "got it"
}

def is_backchannel(text: str) -> bool:
    """
    Returns True if the text contains ONLY words from the IGNORE_WORDS list.
    """
    normalized = "".join(c for c in text.lower() if c.isalnum() or c.isspace())
    words = normalized.split()
    
    if not words:
        return True
    
    return all(word in IGNORE_WORDS for word in words)

async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    base_vad = silero.VAD.load()
    base_stt = openai.STT(model="whisper-1")
    
    # Wrap VAD to skip short utterances
    class BackchannelFilterVAD:
        def __init__(self, vad, stt, initial_buffer_ms: int = 150):
            self._vad = vad
            self._stt = stt
            # how much audio to buffer before validating with STT
            self.initial_buffer_ms = initial_buffer_ms

        @property
        def sample_rate(self):
            return self._vad.sample_rate

        @property
        def channels(self):
            return self._vad.channels

        @property
        def stream(self):
            """
            Async generator that reads the underlying VAD stream, but when speech is
            detected it buffers a short window, validates with STT and only yields
            the buffered frames if the utterance is NOT a backchannel.
            """
            async def _gen():
                it = self._vad.stream.__aiter__()
                loop = asyncio.get_event_loop()

                def _frame_bytes(f):
                    # try common names for raw audio bytes on the frame
                    for attr in ("audio", "data", "samples", "pcm"):
                        val = getattr(f, attr, None)
                        if isinstance(val, (bytes, bytearray)):
                            return bytes(val)
                    # fallback: try to stringify
                    return b""

                try:
                    while True:
                        frame = await it.__anext__()
                        # non-speech frames: pass through immediately
                        if not getattr(frame, "speech", False):
                            yield frame
                            continue

                        # speech detected -> buffer a short window
                        buffer_frames = [frame]
                        start_t = loop.time()
                        timeout = self.initial_buffer_ms / 1000.0

                        # collect frames from underlying iterator for the short window
                        while (loop.time() - start_t) < timeout:
                            try:
                                next_frame = await asyncio.wait_for(it.__anext__(), timeout=timeout - (loop.time() - start_t))
                            except asyncio.TimeoutError:
                                break
                            except StopAsyncIteration:
                                break
                            buffer_frames.append(next_frame)
                            # if speech ended early, break (we still validate what we have)
                            if not getattr(next_frame, "speech", False):
                                break

                        # assemble audio bytes for STT validation
                        audio_bytes = b"".join(_frame_bytes(f) for f in buffer_frames)

                        # run a quick STT check (best-effort). If STT fails, treat as real speech.
                        is_back = False
                        try:
                            stt_result = await self._stt.recognize(audio_bytes)
                            if stt_result:
                                text = stt_result.text if hasattr(stt_result, "text") else str(stt_result)
                                if text and is_backchannel(text):
                                    is_back = True
                        except Exception:
                            # on STT error, assume it's real speech to avoid dropping valid input
                            is_back = False

                        if is_back:
                            # suppress buffered frames (do not yield them) -> agent audio continues uninterrupted
                            logging.debug("Backchannel suppressed by VAD+STT gate")
                            # continue reading stream (we already advanced iterator)
                            continue
                        else:
                            # forward buffered frames, then continue normal streaming (iterator is already at next frame)
                            for bf in buffer_frames:
                                yield bf
                            # resume outer loop (it will continue from the iterator state)
                except StopAsyncIteration:
                    return

            return _gen()

        # keep compatibility with sync API surface
        def process(self, audio_chunk):
            return self._vad.process(audio_chunk)
        
        @property
        def sample_rate(self):
            return self._vad.sample_rate
        
        @property
        def channels(self):
            return self._vad.channels
        
        @property
        def stream(self):
            return self._vad.stream
    
    # Wrap STT to filter backchannel words
    class BackchannelFilterSTT:
        def __init__(self, stt):
            self._stt = stt
        
        async def recognize(self, buffer, language=None, **kwargs):
            result = await self._stt.recognize(buffer, language=language, **kwargs)
            # If it's only a backchannel, return None to prevent interruption
            if result:
                text = result.text if hasattr(result, 'text') else str(result)
                if text and is_backchannel(text):
                    logging.info(f"Filtered backchannel: {text}")
                    return None
            return result
        
        def asr_engine(self):
            return self._stt.asr_engine()
        
        @property
        def capabilities(self):
            return self._stt.capabilities
        
        def on(self, event: str, *args, **kwargs):
            """Delegate event handler registration to the underlying STT"""
            return self._stt.on(event, *args, **kwargs)
    
    agent = Agent(
        vad=BackchannelFilterVAD(base_vad, base_stt, initial_buffer_ms=100),
        stt=BackchannelFilterSTT(base_stt),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="alloy"),
        instructions="You are a helpful voice assistant.",
        allow_interruptions=True
    )

    session = AgentSession()

    await session.start(agent, room=ctx.room)

    await session.say(
        "Hello! I am ready. You can say 'yeah' or 'uh-huh' while I speak, and I will continue seamlessly. "
        "Try saying 'yeah' while I'm speaking and I won't stop. But if you say 'stop' or 'wait', I will interrupt myself.",
        allow_interruptions=True
    )
    
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        logging.info("Agent session cancelled")
        raise

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))