import logging
import ssl
import asyncio
import inspect
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
import os
from datetime import datetime

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

    # log file (placed in current working directory)
    LOG_PATH = os.path.join(os.getcwd(), "interaction_log.txt")

    def _append_log(role: str, text: str, action: str):
        ts = datetime.utcnow().isoformat()
        line = f"{ts}\t{role}\t{action}\t{text}\n"
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception:
            logging.exception("failed to write interaction log")

    # track agent speaking state for decisioning/logging
    is_agent_speaking = False

    # Wrap VAD to skip short utterances and log transcripts
    class BackchannelFilterVAD:
        def __init__(self, vad, stt, initial_buffer_ms: int = 150):
            self._vad = vad
            self._stt = stt
            self.initial_buffer_ms = initial_buffer_ms

        @property
        def sample_rate(self):
            return getattr(self._vad, "sample_rate", 16000)

        @property
        def channels(self):
            return getattr(self._vad, "channels", 1)

        def stream(self):
            """
            Callable expected by the framework. Returns an async generator that
            buffers a short window on speech start, runs a quick STT check and
            suppresses buffered frames if it's a backchannel.
            """
            async def _gen():
                # underlying VAD.stream may be callable or an async iterable
                vad_stream = self._vad.stream() if callable(getattr(self._vad, "stream", None)) else self._vad.stream
                it = vad_stream.__aiter__()
                loop = asyncio.get_event_loop()

                def _frame_bytes(f):
                    for attr in ("audio", "data", "samples", "pcm"):
                        val = getattr(f, attr, None)
                        if isinstance(val, (bytes, bytearray)):
                            return bytes(val)
                    return b""

                try:
                    while True:
                        frame = await it.__anext__()
                        if not getattr(frame, "speech", False):
                            yield frame
                            continue

                        buffer_frames = [frame]
                        start_t = loop.time()
                        timeout = self.initial_buffer_ms / 1000.0

                        while (loop.time() - start_t) < timeout:
                            try:
                                nxt = await asyncio.wait_for(it.__anext__(), timeout=timeout - (loop.time() - start_t))
                            except asyncio.TimeoutError:
                                break
                            except StopAsyncIteration:
                                break
                            buffer_frames.append(nxt)
                            if not getattr(nxt, "speech", False):
                                break

                        audio_bytes = b"".join(_frame_bytes(f) for f in buffer_frames)

                        is_back = False
                        try:
                            stt_result = await self._stt.recognize(audio_bytes)
                            if stt_result:
                                text = stt_result.text if hasattr(stt_result, "text") else str(stt_result)
                                if is_agent_speaking:
                                    if text and is_backchannel(text):
                                        _append_log("USER", text, "ignored_while_agent_speaking")
                                        is_back = True
                                    else:
                                        _append_log("USER", text, "interrupt_requested_while_speaking")
                                else:
                                    _append_log("USER", text, "user_spoke_while_agent_silent")
                        except Exception:
                            logging.debug("quick STT validation failed; treating as real speech")
                            is_back = False

                        if is_back:
                            logging.debug("Backchannel suppressed by VAD+STT gate")
                            continue

                        for bf in buffer_frames:
                            yield bf
                except StopAsyncIteration:
                    return

            return _gen()

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
    
    # Wrap STT to allow backchannels to be processed only when agent is silent; log events.
    class BackchannelFilterSTT:
        def __init__(self, stt):
            self._stt = stt
        
        async def recognize(self, buffer, language=None, **kwargs):
            result = await self._stt.recognize(buffer, language=language, **kwargs)
            if result:
                text = result.text if hasattr(result, "text") else str(result)
                if text:
                    interruption_words = {"stop", "wait", "no", "pause", "hold"}
                    tokens = {t.strip('.,!?;:\'"').lower() for t in text.split() if t.strip()}
                    if tokens & interruption_words:
                        _append_log("USER", text, "interrupt_requested")
                        return result

                    # backchannel handling: if agent speaking -> suppress (return None),
                    # if agent silent -> allow (return result) so agent can respond
                    if is_backchannel(text):
                        if is_agent_speaking:
                            _append_log("USER", text, "ignored_while_agent_speaking")
                            return None
                        else:
                            _append_log("USER", text, "processed_while_agent_silent")
                            return result

                    _append_log("USER", text, "normal_utterance")
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
        allow_interruptions=True,
    )

    session = AgentSession()

    # track agent speak state and log agent utterances (start/stop)
    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        nonlocal is_agent_speaking
        prev = is_agent_speaking
        is_agent_speaking = ev.new_state == "speaking"
        if is_agent_speaking and not prev:
            _append_log("AGENT", "<agent started speaking>", "agent_started")
        elif not is_agent_speaking and prev:
            _append_log("AGENT", "<agent stopped speaking>", "agent_stopped")

    # optional: log committed user speech events if emitted by session
    @session.on("user_input_transcribed")
    def _on_user_transcribed(ev):
        try:
            text = ev.transcript if hasattr(ev, "transcript") else str(ev)
        except Exception:
            text = ""
        if text:
            _append_log("USER", text, "final_transcript_event")

    await session.start(agent, room=ctx.room)

    # log the initial agent message
    _append_log("AGENT", "Initial greeting queued", "agent_initial_greeting")
    await session.say(
        "Hello! I am ready. You can say 'yeah' or 'uh-huh' while I speak, and I will continue seamlessly. "
        "Try saying 'yeah' while I'm speaking and I won't stop. But if you say 'stop' or 'wait', I will interrupt myself.",
        allow_interruptions=True,
    )

    # ---- session method wrappers: log agent text when it speaks ----
    # Wrap session.say so every TTS call is logged
    if hasattr(session, "say"):
        _orig_say = session.say
        async def _say_logger(*args, **kwargs):
            # extract text if present
            text = ""
            if args:
                first = args[0]
                text = first if isinstance(first, str) else str(first)
            elif "text" in kwargs:
                text = str(kwargs["text"])
            _append_log("AGENT", text, "agent_speaking")
            return await _orig_say(*args, **kwargs)
        session.say = _say_logger

    # Wrap session.generate_reply (if present) to log requested reply instructions
    if hasattr(session, "generate_reply"):
        _orig_generate = session.generate_reply
        if inspect.iscoroutinefunction(_orig_generate):
            async def _gen_logger(*args, **kwargs):
                instr = kwargs.get("instructions") or (args[0] if args else "")
                _append_log("AGENT", str(instr), "agent_generate_reply_requested")
                return await _orig_generate(*args, **kwargs)
            session.generate_reply = _gen_logger
        else:
            def _gen_logger(*args, **kwargs):
                instr = kwargs.get("instructions") or (args[0] if args else "")
                _append_log("AGENT", str(instr), "agent_generate_reply_requested")
                return _orig_generate(*args, **kwargs)
            session.generate_reply = _gen_logger

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        logging.info("Agent session cancelled")
        raise

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))