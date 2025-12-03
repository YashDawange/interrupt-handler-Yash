# examples/my_agent/agent.py
import asyncio
import logging
import os
import re
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# ------------------------------
# Logging & env
# ------------------------------
logger = logging.getLogger("interrupt-agent")
logging.basicConfig(level=logging.INFO)
load_dotenv()

# ------------------------------
# Config helpers & defaults
# ------------------------------
def csv_env(name, fallback):
    raw = os.getenv(name, None)
    if not raw:
        return set(fallback)
    return {w.strip().lower() for w in raw.split(",") if w.strip()}

DEFAULT_SOFT = ["yeah", "ok", "okay", "hmm", "uh-huh", "right", "yep", "sure", "mmhmm", "yup", "uh"]
DEFAULT_HARD = ["stop", "wait", "no", "cancel", "pause", "hold", "hold on", "hold-up", "stop now"]

SOFT_IGNORE = csv_env("IGNORE_WORDS", DEFAULT_SOFT)
HARD_WORDS = csv_env("INTERRUPT_WORDS", DEFAULT_HARD)

# delays (seconds) - tunable via env
STT_FINALIZE_DELAY = float(os.getenv("STT_FINALIZE_DELAY", "0.12"))
GRACE_WINDOW = float(os.getenv("GRACE_WINDOW", "0.18"))  # micro-window to let STT finalize during speaking

# regex tokenizer
word_re = re.compile(r"[A-Za-z0-9'-]+")

def tokenize(text: str):
    return [w.lower() for w in word_re.findall(text)]

def tokens_set(text: str):
    return set(tokenize(text))

def is_all_soft(tokens):
    return tokens and all(t in SOFT_IGNORE for t in tokens)

def has_hard(tokens):
    return any(t in HARD_WORDS for t in tokens)

# ------------------------------
# Agent class
# ------------------------------
class MyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "Your name is Kelly. Speak short, concise English. "
                "Do not use emojis or markdown."
            )
        )

    async def on_enter(self):
        # seed initial reply
        self.session.generate_reply()

# ------------------------------
# Server prewarm
# ------------------------------
server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

# ------------------------------
# Main RTC Session Entrypoint
# ------------------------------
@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # Create session with turn detection; tune parameters if needed
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
        # Keep interruptions enabled but rely on our logic layer to decide when to call session.interrupt()
        allow_interruptions=True,
        discard_audio_if_uninterruptible=True,
        preemptive_generation=False,
    )

    # usage collector
    usage = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _collect(ev: MetricsCollectedEvent):
        usage.collect(ev.metrics)

    # ------------------------------
    # State
    # ------------------------------
    agent_is_speaking = False

    # main user transcript buffer used when agent is NOT speaking (committed at end-of-speech)
    transcript_buffer = ""
    buffer_lock = asyncio.Lock()

    # soft temporary buffer used while agent is speaking to accumulate STT for the grace-window
    speaking_temp = ""
    speaking_temp_lock = asyncio.Lock()
    speaking_grace_task = None  # asyncio.Task for grace-window checker
    speaking_grace_lock = asyncio.Lock()

    interrupt_queue = asyncio.Queue()

    # last STT received (helpful fallback)
    last_transcription = ""
    last_transcription_lock = asyncio.Lock()

    # ------------------------------
    # Agent state changes
    # ------------------------------
    @session.on("agent_state_changed")
    def _on_agent_state(ev):
        nonlocal agent_is_speaking, speaking_temp, speaking_grace_task
        agent_is_speaking = (ev.new_state == "speaking")
        logger.info(f"[STATE] agent_is_speaking={agent_is_speaking}")

        if agent_is_speaking:
            # reset any leftover buffers when agent starts speaking
            # ensure the speaking temp is cleared for a fresh segment
            async def _clear():
                nonlocal speaking_temp
                async with speaking_temp_lock:
                    speaking_temp = ""
            asyncio.create_task(_clear())
        else:
            # if agent stopped speaking, cancel any pending grace check
            async def _cancel_grace():
                nonlocal speaking_grace_task
                async with speaking_grace_lock:
                    if speaking_grace_task and not speaking_grace_task.done():
                        speaking_grace_task.cancel()
                    speaking_grace_task = None
            asyncio.create_task(_cancel_grace())

    # ------------------------------
    # Transcription event (fast path)
    # ------------------------------
    @session.on("transcription")
    def _on_transcription(ev):
        """
        ev may have .text or .alternatives[].text
        We handle quick decisions here by creating tasks for process_stt.
        """
        text = ""
        if hasattr(ev, "text"):
            text = ev.text.strip()
        else:
            text = (ev.alternatives[0].text.strip() if getattr(ev, "alternatives", None) else "").strip()

        if not text:
            return

        # store last transcription
        async def _last_update():
            nonlocal last_transcription
            async with last_transcription_lock:
                last_transcription = text
        asyncio.create_task(_last_update())

        # defer to processor
        asyncio.create_task(process_stt(text))

    # ------------------------------
    # Process STT logic
    # ------------------------------
    async def process_stt(text: str):
        """
        Main STT handler implementing:
        - If agent is speaking:
            * immediate interrupt if contains hard words
            * immediate drop if purely soft words
            * else: accumulate into speaking_temp and start micro-grace window
        - If agent is NOT speaking:
            * accumulate into transcript_buffer for commit when VAD says listening (user finished)
        """
        nonlocal transcript_buffer, agent_is_speaking, speaking_temp, speaking_grace_task

        tokens = tokens_set(text)
        if not tokens:
            return

        # ------------------------------
        # If agent is speaking -> use immediate rules
        # ------------------------------
        if agent_is_speaking:
            # immediate hard interrupt -> schedule interrupt
            if has_hard(tokens):
                logger.info(f"[HARD] Detected while speaking -> queue interrupt: '{text}'")
                await interrupt_queue.put("INT")
                return

            # purely soft -> drop immediately (no buffer change)
            if is_all_soft(tokens):
                logger.debug(f"[SOFT] Dropped while speaking (pure filler): '{text}'")
                return

            # Mixed or ambiguous phrase -> collect micro-window of STT, then decide
            # Add current text to speaking_temp and start (or restart) the grace timer.
            async with speaking_temp_lock:
                speaking_temp += " " + text

            # (re)start the grace timer which will evaluate the accumulated speaking_temp
            async with speaking_grace_lock:
                if speaking_grace_task and not speaking_grace_task.done():
                    # let the existing task finish - restart by cancelling and creating new
                    try:
                        speaking_grace_task.cancel()
                    except Exception:
                        pass
                speaking_grace_task = asyncio.create_task(_evaluate_speaking_temp_after_grace())
            return

        # ------------------------------
        # Agent NOT speaking -> accumulate into main buffer
        # ------------------------------
        async with buffer_lock:
            transcript_buffer += " " + text
            logger.debug(f"[BUFFER] Accumulated while not speaking: '{text}'")

    # ------------------------------
    # Evaluate speaking_temp after grace window
    # ------------------------------
    async def _evaluate_speaking_temp_after_grace():
        """
        Waits GRACE_WINDOW seconds to collect any trailing STT pieces.
        Then decides:
          - if any hard words -> interrupt
          - else if after trimming only soft words -> drop (do nothing)
          - else if non-soft tokens but no hard tokens -> treat as ambiguous: to preserve continuity, we drop (do not interrupt).
            (This choice preserves 'no pause' requirement; mixed input with explicit command will include a hard word and interrupt.)
        """
        nonlocal speaking_temp
        try:
            await asyncio.sleep(GRACE_WINDOW)
        except asyncio.CancelledError:
            # cancelled because new STT arrived and we'll run later
            return

        async with speaking_temp_lock:
            temp = speaking_temp.strip()
            # reset buffer for next speaking stretch
            speaking_temp = ""

        if not temp:
            return

        tokens = tokens_set(temp)
        # immediate if any hard words
        if has_hard(tokens):
            logger.info(f"[GRACE->HARD] After grace window, interrupting for: '{temp}'")
            await interrupt_queue.put("INT")
            return

        # if only soft words -> drop
        if is_all_soft(tokens):
            logger.debug(f"[GRACE->SOFT] After grace window, dropping pure filler: '{temp}'")
            return

        # Mixed but no explicit hard tokens — we choose to drop (preserve audio continuity)
        # Log for visibility
        logger.debug(f"[GRACE->DROP] After grace window, ambiguous phrase dropped to keep continuity: '{temp}'")
        return

    # ------------------------------
    # User state changes -> end-of-speech detection
    # When user_state changes to 'listening', user just stopped speaking.
    # Wait short STT_FINALIZE_DELAY to let STT finalize before committing.
    # ------------------------------
    @session.on("user_state_changed")
    def _on_user_state(ev):
        if ev.new_state == "listening":
            asyncio.create_task(_on_end_of_speech())

    async def _on_end_of_speech():
        nonlocal transcript_buffer, last_transcription

        # Wait a short time for STT finalization (partial -> final)
        await asyncio.sleep(STT_FINALIZE_DELAY)

        # Prefer accumulated buffer (which may have multiple STT chunks). If empty, fallback to last transcription.
        async with buffer_lock:
            buff = transcript_buffer.strip()
            transcript_buffer = ""

        async with last_transcription_lock:
            stt_final = last_transcription.strip()

        final_text = buff if buff else stt_final

        if not final_text:
            # nothing to commit (possible false VAD)
            return

        logger.info(f"[USER] Final utterance (committing): '{final_text}'")
        # Commit user turn so LLM sees the user input
        await session.commit_user_turn()

    # ------------------------------
    # Interrupt worker -> performs real session.interrupt()
    # This is decoupled so transcription processing stays fast and non-blocking.
    # ------------------------------
    async def interrupt_worker():
        while True:
            sig = await interrupt_queue.get()
            if sig == "INT":
                logger.info(">>> EXECUTING HARD INTERRUPT NOW <<<")
                try:
                    # session.interrupt() is the API to stop current TTS/LLM speaking
                    await session.interrupt()
                except Exception as e:
                    logger.exception("Interrupt failed: %s", e)

    asyncio.create_task(interrupt_worker())

    # ------------------------------
    # Start session
    # ------------------------------
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )

# ------------------------------
# Run
# ------------------------------
if __name__ == "__main__":
    cli.run_app(server)
