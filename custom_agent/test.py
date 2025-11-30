

import logging
import string
import asyncio
import uuid
import time
from typing import Optional, Dict

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RunContext,
    cli,
    metrics,
    room_io,
    stt,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel



LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
logger = logging.getLogger("basic-agent")

def _handle_async_exception(loop, context):
    logger.error("UNHANDLED ASYNC EXCEPTION: %s", context)

loop = asyncio.get_event_loop()
loop.set_exception_handler(_handle_async_exception)

load_dotenv()




IGNORE_WORDS = {
    "yeah", "yea", "yep", "yup", "ya", "yah",
    "ok", "okay", "k", "kk", "okey",
    "hmm", "mm", "mhm", "uh", "uhh", "umm", "um",
    "right", "sure", "cool", "fine",
    "okayyy", "okk", "okayy",
    "yes", "yess", "yesss",
    "alright", "aight",
    "gotcha", "gotchaa",
    "true", "tru", "ture",
    "huh", "aha",
}
IGNORE_PHRASES = {
    "yeah yeah",
    "yeah ok",
    "yeah okay",
    "ok ok",
    "ok okay",
    "okay okay",
    "yes yes",
    "yea yea",
    "yep yep",
    "right right",
    "mhm yeah",
    "hmm yeah",
    "okay right",
    "alright alright",
    "i see",
    "sounds good",
    "got it",
    "makes sense",
    "fair enough",
}

INTERRUPT_KEYWORDS = {
    "stop", "shut up", "no", "no stop", "wait", "hold on", "stop now", "pause",
    "cut", "listen", "someone called", "hey", "hello", "what", "why", "stop it"
}
PROFANITY_INTERRUPTS = {"shit", "damn"}

CONFIDENCE_THRESHOLD = 0.60
HIGH_CONFIDENCE_PARTIAL = 0.85  
REPEATED_PASSIVE_THRESHOLD = 3
REPEATED_PASSIVE_WINDOW = 3.0  
QUESTION_RESPONSE_WINDOW = 4.0  


ECHO_SUPPRESSION_WINDOW = 0.35  

def normalize_text(text: str) -> str:
    if not text:
        return ""
    s = text.lower().strip()
    s = s.translate(str.maketrans("", "", string.punctuation))
    s = " ".join(s.split())
    return s

def extract_confidence(ev: stt.SpeechEvent) -> float:
    try:
        if not ev.alternatives:
            return 0.5
        alt0 = ev.alternatives[0]
        conf = getattr(alt0, "confidence", None)
        if conf is None:
            conf = getattr(alt0, "score", None)
        if conf is None:
            return 0.5
        return float(conf)
    except Exception:
        return 0.5

class SlidingWindowCounter:
    def __init__(self, window_s: float):
        self.window = window_s
        self.timestamps = []

    def add(self, t: float):
        self.timestamps.append(t)
        cutoff = t - self.window
        self.timestamps = [ts for ts in self.timestamps if ts >= cutoff]

    def count(self, now: float) -> int:
        cutoff = now - self.window
        return len([ts for ts in self.timestamps if ts >= cutoff])

def contains_interrupt_keyword(normalized: str) -> bool:
    if not normalized:
        return False
    for phrase in INTERRUPT_KEYWORDS:
        if phrase in normalized:
            return True
    for p in PROFANITY_INTERRUPTS:
        if p in normalized:
            return True
    return False

def is_pure_backchannel(normalized: str) -> bool:
    if not normalized:
        return False
    if normalized in IGNORE_PHRASES:
        return True
    toks = normalized.split()
    return bool(toks) and all(tok in IGNORE_WORDS for tok in toks)


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. Read continuously; ignore backchannels while speaking; "
                "accept backchannels as answers when silent and recently asked a question."
            )
        )

    async def on_enter(self):
        logger.info("Agent.on_enter: starting opening generation (interruptible).")
        await self.generate_reply(allow_interruptions=True)

    @function_tool
    async def lookup_weather(self, context: RunContext, location: str):
        logger.debug("lookup_weather called location=%s", location)
        return "sunny with a temperature of 70 degrees."



server = AgentServer()

def prewarm(proc: JobProcess):
    logger.info("Prewarming VAD and storing on proc.userdata['vad']")
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("Entrypoint started for room=%s", ctx.room.name)

    session_allow_interruptions = True
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        allow_interruptions=session_allow_interruptions,
        preemptive_generation=True,
    )

    logger.info("Starting AgentSession for room=%s (session_allow_interruptions=%s)",
                ctx.room.name, session_allow_interruptions)

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        logger.debug("metrics_collected: %s", ev.metrics)
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    # trackers
    last_agent_question_ts: Optional[float] = None
    passive_counter = SlidingWindowCounter(REPEATED_PASSIVE_WINDOW)



    last_agent_state: Optional[str] = None
    last_agent_speech_end: Optional[float] = None

    trace_map: Dict[str, dict] = {}

    async def _try_interrupt(trace_id: str):
        try:
            logger.debug("[%s] _try_interrupt: calling session.interrupt()", trace_id)
            await session.interrupt()
            logger.info("[%s] _try_interrupt: interrupt succeeded", trace_id)
        except RuntimeError as e:
            logger.warning("[%s] _try_interrupt: interrupt rejected: %s", trace_id, e)
        except Exception as e:
            logger.exception("[%s] _try_interrupt: unexpected error: %s", trace_id, e)

    @session.on("user_transcription")
    def on_user_transcription(ev: stt.SpeechEvent):
        nonlocal last_agent_question_ts, last_agent_state, last_agent_speech_end
        try:
            trace_id = str(uuid.uuid4())
            trace_map[trace_id] = {"recv_ts": time.time()}

            if not ev.alternatives:
                logger.debug("[%s] no alternatives; skipping", trace_id)
                return

            alt0 = ev.alternatives[0]
            raw_text = getattr(alt0, "text", "") or ""
            raw_text = raw_text.strip()
            normalized = normalize_text(raw_text)
            confidence = extract_confidence(ev)


            is_final = getattr(ev, "is_final", None)
            if is_final is None:
                is_final = getattr(alt0, "is_final", True)
            is_final = bool(is_final)

            trace_map[trace_id].update({
                "raw_text": raw_text, "normalized": normalized,
                "confidence": confidence, "is_final": is_final
            })

            logger.debug("[%s] transcript=%r normalized=%r conf=%.2f final=%s",
                         trace_id, raw_text, normalized, confidence, is_final)


            agent_state = None
            try:
                agent_state = session.agent.state if getattr(session, "agent", None) else None
            except Exception:
                logger.exception("[%s] reading session.agent.state failed", trace_id)
            trace_map[trace_id]["agent_state"] = agent_state
            logger.debug("[%s] agent_state=%r", trace_id, agent_state)


            now = time.time()
            try:
                if last_agent_state is None:
                    last_agent_state = agent_state
                else:
                    if last_agent_state in ("speaking", "thinking") and agent_state not in ("speaking", "thinking"):
                        # agent just stopped speaking
                        last_agent_speech_end = now
                        logger.debug("Detected agent->stopped at ts=%.3f (state=%r)", last_agent_speech_end, agent_state)
                    last_agent_state = agent_state
            except Exception:
                logger.exception("[%s] while updating last_agent_state", trace_id)


            if last_agent_speech_end:
                since_agent_end = now - last_agent_speech_end
            else:
                since_agent_end = None


            token_count = len([t for t in normalized.split() if t])


            if not is_final and confidence < HIGH_CONFIDENCE_PARTIAL:
                logger.debug("[%s] ignoring low-confidence partial (conf=%.2f final=%s)", trace_id, confidence, is_final)
                return


            if since_agent_end is not None and since_agent_end <= ECHO_SUPPRESSION_WINDOW and token_count <= 1:
                logger.info("[%s] Ignoring probable echo: arrived %.3fs after agent speech end, token_count=%d normalized=%r",
                            trace_id, since_agent_end, token_count, normalized)
                return


            agent_recent_question = last_agent_question_ts and (now - last_agent_question_ts <= QUESTION_RESPONSE_WINDOW)


            if agent_state in ("speaking", "thinking"):
                if contains_interrupt_keyword(normalized) and confidence >= (CONFIDENCE_THRESHOLD * 0.5):
                    logger.info("[%s] explicit-interrupt detected while speaking: %r conf=%.2f", trace_id, normalized, confidence)
                    try:
                        asyncio.create_task(_try_interrupt(trace_id))
                    except RuntimeError:
                        loop = asyncio.get_event_loop()
                        loop.create_task(_try_interrupt(trace_id))
                    return


                if is_pure_backchannel(normalized):
                    passive_counter.add(now)
                    count = passive_counter.count(now)
                    logger.info("[%s] pure backchannel while speaking (count=%d): %r -> IGNORE", trace_id, count, normalized)
                    if count >= REPEATED_PASSIVE_THRESHOLD:
                        logger.warning("[%s] repeated passive threshold exceeded -> escalate to interrupt", trace_id)
                        try:
                            asyncio.create_task(_try_interrupt(trace_id))
                        except RuntimeError:
                            loop = asyncio.get_event_loop()
                            loop.create_task(_try_interrupt(trace_id))
                    return


                if token_count >= 2 and confidence >= CONFIDENCE_THRESHOLD:
                    logger.info("[%s] multi-token non-passive utterance while speaking -> interrupt (tokens=%d conf=%.2f)",
                                trace_id, token_count, confidence)
                    try:
                        asyncio.create_task(_try_interrupt(trace_id))
                    except RuntimeError:
                        loop = asyncio.get_event_loop()
                        loop.create_task(_try_interrupt(trace_id))
                    return


                logger.debug("[%s] ambiguous/low-confidence input while speaking -> ignore (normalized=%r conf=%.2f)", trace_id, normalized, confidence)
                return


            if agent_recent_question and is_pure_backchannel(normalized):
                logger.info("[%s] accepting backchannel as answer to recent question: %r conf=%.2f", trace_id, normalized, confidence)
                return

            if token_count == 1:
                if confidence < CONFIDENCE_THRESHOLD:
                    logger.info("[%s] ignoring single-token low-confidence utterance while agent silent (normalized=%r conf=%.2f)", trace_id, normalized, confidence)
                    return
                logger.debug("[%s] single-token high-confidence utterance accepted while agent silent (normalized=%r conf=%.2f)", trace_id, normalized, confidence)
                return

            logger.debug("[%s] letting session process input while agent silent: normalized=%r tokens=%d conf=%.2f", trace_id, normalized, token_count, confidence)
            return

        except Exception as e:
            logger.exception("Exception in on_user_transcription handler: %s", e)

    async def question_detector():
        nonlocal last_agent_question_ts, last_agent_state, last_agent_speech_end
        last_text_seen = None
        while True:
            try:
                agent_obj = getattr(session, "agent", None)
                if agent_obj is not None:
                    last_reply = getattr(agent_obj, "last_reply", None) or getattr(agent_obj, "_last_reply_text", None)
                    cur_state = None
                    try:
                        cur_state = getattr(agent_obj, "state", None)
                    except Exception:
                        cur_state = None

                    if last_reply and last_reply != last_text_seen:
                        last_text_seen = last_reply
                        if "?" in last_reply or last_reply.strip().lower().startswith(("do ", "are ", "is ", "was ", "did ", "have ", "could ", "would ", "can ")):
                            last_agent_question_ts = time.time()
                            logger.debug("question_detector: detected agent question: %r (ts=%s)", last_reply, last_agent_question_ts)

                    try:
                        if last_agent_state is None:
                            last_agent_state = cur_state
                        else:
                            if last_agent_state in ("speaking", "thinking") and cur_state not in ("speaking", "thinking"):
                                last_agent_speech_end = time.time()
                                logger.debug("question_detector: detected agent stopped speaking at ts=%.3f", last_agent_speech_end)
                            last_agent_state = cur_state
                    except Exception:
                        logger.exception("question_detector: state transition read failed")

                await asyncio.sleep(0.20)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Exception in question_detector loop")
                await asyncio.sleep(0.5)

    question_detector_task = asyncio.create_task(question_detector())

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info("Usage summary: %s", summary)

    ctx.add_shutdown_callback(log_usage)

    try:
        await session.start(
            agent=MyAgent(),
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(),
            ),
        )
    finally:
        question_detector_task.cancel()
        try:
            await question_detector_task
        except Exception:
            pass

if __name__ == "__main__":
    logger.info("Starting agent server (CLI)")
    cli.run_app(server)
