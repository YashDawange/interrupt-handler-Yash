import logging
import asyncio
import os
from typing import Set, List

from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.plugins import deepgram, silero
from livekit import rtc

load_dotenv()

# set logging to see everything
logger = logging.getLogger("logic-agent")
logger.setLevel(logging.INFO)

server = AgentServer()

# --- configuration ---
IGNORE_WORDS: Set[str] = {
    "yeah", "yea", "ok", "okay", "hmm", "mhmm", "aha", "uh-huh", "right"
}

START_WORDS: Set[str] = {
    "start", "begin", "continue", "resume", "go on", "okay", "yeah", "hello"
}

MONOLOGUE_CHUNKS: List[str] = [
    "I am now starting the explanation of LiveKit.",
    "LiveKit is an open source infrastructure for real time audio and video.",
    "It allows developers to build scalable, multi user conferencing applications.",
    "The core of LiveKit is the Selective Forwarding Unit, or SFU.",
    "This server receives media tracks from publishers and forwards them to subscribers.",
    "Unlike a traditional MCU, an SFU does not decode and re encode the media.",
    "This architecture allows for significantly lower latency and CPU usage on the server.",
    "LiveKit provides SDKs for all major platforms, including Web, iOS, Android, and Unity.",
    "These SDKs handle the complexities of WebRTC signaling and media negotiation.",
    "Developers can also use the LiveKit Agents framework to build AI participants.",
    "Agents can listen to audio, process it with an LLM, and speak back in real time.",
    "This enables powerful use cases like voice assistants, translators, and game NPCs.",
    "The LiveKit ecosystem also includes Egress for recording and Ingress for RTMP input.",
    "Overall, LiveKit simplifies the challenge of building real time communication apps.",
    "This concludes the explanation. System shutting down."
]

state = {
    "is_speaking": False,      
    "interrupted": False,      
    "current_index": 0,
    "audio_source": None
}

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    await ctx.connect()
    
    # setup plugins
    tts = deepgram.TTS()
    stt = deepgram.STT(model="nova-2")
    vad = silero.VAD.load()

    # 1. setup audio output (standard 24000hz for deepgram aura)
    # if the voice sounds deep/slow, change this to 48000
    # if the voice sounds high/chipmunk, change this to 16000
    SAMPLE_RATE = 24000 
    state["audio_source"] = rtc.AudioSource(SAMPLE_RATE, 1)
    track = rtc.LocalAudioTrack.create_audio_track("agent-mic", state["audio_source"])
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await ctx.room.local_participant.publish_track(track, options)
    logger.info("mouth configured")

    # --- audio engine ---
    async def play_audio(text_chunks: List[str]):
        state["is_speaking"] = True
        state["interrupted"] = False
        source = state["audio_source"]

        logger.info(f"playback requested")

        for i, text_chunk in enumerate(text_chunks):
            if state["interrupted"]: break

            try:
                logger.info(f"   generating tts: '{text_chunk[:15]}...'")
                stream = tts.synthesize(text_chunk)
                
                async for ev in stream:
                    if state["interrupted"]: break
                    
                    # extract frame (safe method)
                    frame = getattr(ev, 'frame', None)
                    
                    if frame is not None:
                        data_len = len(frame.data)
                        # logger.info(f"tts data: {data_len} bytes") # uncomment to debug raw data
                        
                        await source.capture_frame(frame)
                        
                        # sync sleep (2 bytes per sample)
                        duration = data_len / (SAMPLE_RATE * 2)
                        await asyncio.sleep(duration)
                
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"tts error: {e}")

        if not state["interrupted"]:
            state["is_speaking"] = False
            logger.info("playback finished naturally.")
            if text_chunks is MONOLOGUE_CHUNKS:
                state["current_index"] = 0 

    async def stop_speaking():
        if state["is_speaking"]:
            logger.info("stop command received.")
            state["interrupted"] = True
            state["is_speaking"] = False

    # --- logic brain ---
    def handle_text(text: str):
        clean_text = "".join(c for c in text.strip().lower() if c.isalnum() or c.isspace())
        if not clean_text: return

        current_state = "SPEAKING" if state["is_speaking"] else "SILENT"
        logger.info(f"logic: '{clean_text}' | state: {current_state}")

        # [req 3] if speaking
        if state["is_speaking"]:
            if clean_text in IGNORE_WORDS:
                logger.info(f"   ignored (backchannel)")
                return
            else:
                logger.info(f"   interrupt triggered")
                state["current_index"] += 1
                if state["current_index"] >= len(MONOLOGUE_CHUNKS): state["current_index"] = 0
                asyncio.create_task(stop_speaking())
                return

        # [req 4] if silent
        if not state["is_speaking"]:
            if clean_text in START_WORDS:
                logger.info(f"   start command detected")
                remaining_chunks = MONOLOGUE_CHUNKS[state["current_index"]:]
                asyncio.create_task(play_audio(remaining_chunks))
                return
            else:
                logger.info(f"   waiting (not a start word)")

    # --- manual ear (safe mode) ---
    # this bypasses all 'enum' checks that caused crashes before
    async def run_stt(participant: rtc.RemoteParticipant):
        logger.info(f"attaching ear to: {participant.identity}")
        
        audio_track = None
        for pub in participant.track_publications.values():
            if pub.kind == rtc.TrackKind.KIND_AUDIO:
                if not pub.subscribed: pub.set_subscribed(True)
                audio_track = pub.track
                break
        
        if not audio_track:
            logger.warning("   no audio track found yet.")
            return

        stt_stream = stt.stream()
        audio_stream = rtc.AudioStream(audio_track)

        async def send_audio():
            async for event in audio_stream:
                # handle both raw frames and wrapper events
                frame = getattr(event, 'frame', event)
                stt_stream.push_frame(frame)
            stt_stream.flush()

        async def receive_text():
            async for ev in stt_stream:
                # duck typing: if it looks like a transcript, treat it like one.
                # this works on all versions.
                alts = getattr(ev, 'alternatives', None)
                if alts and len(alts) > 0:
                    text = alts[0].text
                    # check for finality safely
                    is_final = getattr(ev, 'is_final', False)
                    # if type exists, check it safely
                    ev_type = getattr(ev, 'type', None)
                    
                    # logic: if it's marked final or it's a significant string
                    if is_final or (ev_type and str(ev_type).endswith("FINAL_TRANSCRIPT")):
                        handle_text(text)

        await asyncio.gather(send_audio(), receive_text())

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(run_stt(participant))

    for participant in ctx.room.remote_participants.values():
        asyncio.create_task(run_stt(participant))

    # initialize dummy session
    session = AgentSession(stt=stt, tts=tts, vad=vad)
    await session.start(agent=Agent(instructions="monitor"), room=ctx.room)
    
    # ready sound
    asyncio.create_task(play_audio(["system ready. say start."]))

if __name__ == "__main__":
    cli.run_app(server)