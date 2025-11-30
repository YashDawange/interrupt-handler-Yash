import asyncio
import uuid
import time
import logging
from typing import Optional, Dict

from livekit.agents import (
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    metrics,
    room_io,
    stt,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from .config import (
    logger as pkg_logger,
    DEFAULT_STT,
    DEFAULT_LLM,
    DEFAULT_TTS,
    CONFIDENCE_THRESHOLD,
    HIGH_CONFIDENCE_PARTIAL,
    REPEATED_PASSIVE_THRESHOLD,
    REPEATED_PASSIVE_WINDOW,
    QUESTION_RESPONSE_WINDOW,
    ECHO_SUPPRESSION_WINDOW,
)
from .utils import (
    normalize_text,
    extract_confidence,
    SlidingWindowCounter,
    contains_interrupt_keyword,
    is_pure_backchannel,
)
from .agent_impl import MyAgent

logger = logging.getLogger("livekit-agent.session")


def prewarm(proc):
    """Prewarm VAD synchronously and store it on proc.userdata['vad']."""
    try:
        logger.info("Prewarming VAD and storing on proc.userdata['vad']")
        proc.userdata["vad"] = silero.VAD.load()
    except Exception as e:
        logger.exception("Prewarm VAD failed: %s", e)


def create_session(room, proc, allow_interruptions=True) -> AgentSession:
    """
    Create an AgentSession. Ensure vad exists (lazy load if missing).
    Also gracefully fall back if MultilingualModel initialization fails.
    """
    # 1) Ensure VAD is present (lazy-load if needed)
    vad = proc.userdata.get("vad")
    if vad is None:
        try:
            logger.info("VAD not found in proc.userdata — loading silero.VAD now")
            vad = silero.VAD.load()
            proc.userdata["vad"] = vad
        except Exception as e:
            logger.exception("Failed to load silero.VAD: %s. Proceeding with vad=None.", e)
            vad = None

    # 2) Try to initialize the multilingual turn detector, but allow None fallback
    turn_detector_instance = None
    try:
        turn_detector_instance = MultilingualModel()
    except Exception as e:
        logger.warning("Could not initialize MultilingualModel (turn detector). Proceeding without it. Error: %s", e)
        turn_detector_instance = None

    # 3) Build session
    return AgentSession(
        stt=DEFAULT_STT,
        llm=DEFAULT_LLM,
        tts=DEFAULT_TTS,
        turn_detection=turn_detector_instance,
        vad=vad,
        allow_interruptions=allow_interruptions,
        preemptive_generation=True,
    )

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("Entrypoint started for room=%s", ctx.room.name)

    session_allow_interruptions = True
    session = create_session(ctx.room, ctx.proc, session_allow_interruptions)

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

            # NEW: If it's a pure backchannel (e.g., "hmm", "yeah", "yep") and the agent is silent,
            # ignore it entirely — we don't want one-word affirmatives to trigger a fresh generation.
            if is_pure_backchannel(normalized):
                logger.info("[%s] pure backchannel while agent silent -> IGNORE: %r conf=%.2f", trace_id, normalized, confidence)
                return

            # Now handle single-token utterances that are NOT pure backchannels.
            if token_count == 1:
                # For single-token non-backchannels, require a minimum confidence before accepting.
                if confidence < CONFIDENCE_THRESHOLD:
                    logger.info("[%s] ignoring single-token low-confidence utterance while agent silent (normalized=%r conf=%.2f)", trace_id, normalized, confidence)
                    return

                # Single-token high-confidence non-backchannels are accepted (rare).
                logger.debug("[%s] single-token high-confidence (non-backchannel) accepted while agent silent (normalized=%r conf=%.2f)", trace_id, normalized, confidence)
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