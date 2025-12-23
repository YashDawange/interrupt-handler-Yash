from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Generator, Sequence
from typing import Any, Callable
import re
import os
import logging

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
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("basic-agent")

load_dotenv()

# --- IGNORE / INTERRUPT WORDS ---
IGNORE_WORDS = set(
    w.replace("-", " ").strip().lower()
    for w in os.getenv("LIVEKIT_IGNORE_WORDS", "yeah,ok,okay,hmm,uh-huh,right,uhm").split(",")
)

INTERRUPT_WORDS = set(
    w.replace("-", " ").strip().lower()
    for w in os.getenv("LIVEKIT_INTERRUPT_WORDS", "stop,wait,no,hold,pause").split(",")
)

def _is_passive_ack(text: str) -> bool:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(words) and words.issubset(IGNORE_WORDS)

def _is_active_interrupt(text: str) -> bool:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(words & INTERRUPT_WORDS)


# --- SPEECH HANDLE ---
class SpeechHandle:
    SPEECH_PRIORITY_LOW = 0
    SPEECH_PRIORITY_NORMAL = 5
    SPEECH_PRIORITY_HIGH = 10

    def on_final_transcript(self, text: str) -> None:
        if not self._pending_interrupt:
            return

        text_normalized = text.lower().replace("-", " ").strip()

        if _is_active_interrupt(text_normalized):
            self._cancel()
        elif _is_passive_ack(text_normalized):
            return
        else:
            self._cancel()

        self._pending_interrupt = False

    def __init__(self, *, speech_id: str, allow_interruptions: bool) -> None:
        self._id = speech_id
        self._allow_interruptions = allow_interruptions
        self._pending_interrupt = False
        self._interrupt_fut = asyncio.Future[None]()
        self._done_fut = asyncio.Future[None]()
        self._scheduled_fut = asyncio.Future[None]()
        self._authorize_event = asyncio.Event()

        self._generations: list[asyncio.Future[None]] = []
        self._tasks: list[asyncio.Task] = []
        self._chat_items: list[Any] = []
        self._num_steps = 1

        self._item_added_callbacks: set[Callable[[Any], None]] = set()
        self._done_callbacks: set[Callable[[SpeechHandle], None]] = set()
        self._is_speaking = False

        def _on_done(_: asyncio.Future[None]) -> None:
            for cb in self._done_callbacks:
                cb(self)

        self._done_fut.add_done_callback(_on_done)
        self._maybe_run_final_output: Any = None

    @staticmethod
    def create(allow_interruptions: bool = True) -> SpeechHandle:
        import uuid
        return SpeechHandle(
            speech_id=str(uuid.uuid4()),
            allow_interruptions=allow_interruptions,
        )

    @property
    def num_steps(self) -> int:
        return self._num_steps

    @property
    def id(self) -> str:
        return self._id

    @property
    def scheduled(self) -> bool:
        return self._scheduled_fut.done()

    @property
    def interrupted(self) -> bool:
        return self._interrupt_fut.done()

    @property
    def allow_interruptions(self) -> bool:
        return self._allow_interruptions

    @allow_interruptions.setter
    def allow_interruptions(self, value: bool) -> None:
        if self.interrupted and not value:
            raise RuntimeError(
                "Cannot set allow_interruptions to False, the SpeechHandle is already interrupted"
            )
        self._allow_interruptions = value

    @property
    def chat_items(self) -> list[Any]:
        return self._chat_items

    def done(self) -> bool:
        return self._done_fut.done()

    def interrupt(self, *, force: bool = False) -> SpeechHandle:
        if not self._allow_interruptions and not force:
            return self
        if self._is_speaking:
            self._pending_interrupt = True
            return self
        self._cancel()
        return self

    async def wait_for_playout(self) -> None:
        from .agent import _get_activity_task_info  # type: ignore
        if task := asyncio.current_task():
            info = _get_activity_task_info(task)
            if info and info.function_call and info.speech_handle == self:
                raise RuntimeError(
                    f"cannot call `SpeechHandle.wait_for_playout()` from inside the function tool `{info.function_call.name}` that owns this SpeechHandle. "
                    "This creates a circular wait."
                )
        await asyncio.shield(self._done_fut)

    def __await__(self) -> Generator[None, None, SpeechHandle]:
        async def _await_impl() -> SpeechHandle:
            await self.wait_for_playout()
            return self
        return _await_impl().__await__()

    def add_done_callback(self, callback: Callable[[SpeechHandle], None]) -> None:
        self._done_callbacks.add(callback)

    def remove_done_callback(self, callback: Callable[[SpeechHandle], None]) -> None:
        self._done_callbacks.discard(callback)

    async def wait_if_not_interrupted(self, aw: list[asyncio.futures.Future[Any]]) -> None:
        fs: list[asyncio.Future[Any]] = [
            asyncio.gather(*aw, return_exceptions=True),
            self._interrupt_fut,
        ]
        await asyncio.wait(fs, return_when=asyncio.FIRST_COMPLETED)

    def _cancel(self) -> SpeechHandle:
        if self.done():
            return self
        with contextlib.suppress(asyncio.InvalidStateError):
            self._interrupt_fut.set_result(None)
        return self

    def _add_item_added_callback(self, callback: Callable[[Any], Any]) -> None:
        self._item_added_callbacks.add(callback)

    def _remove_item_added_callback(self, callback: Callable[[Any], Any]) -> None:
        self._item_added_callbacks.discard(callback)

    def _item_added(self, items: Sequence[Any]) -> None:
        for item in items:
            if item.role == "user" and hasattr(item, "content"):
                self.on_final_transcript(item.content)
            for cb in self._item_added_callbacks:
                cb(item)
            self._chat_items.append(item)

    def _authorize_generation(self) -> None:
        fut = asyncio.Future[None]()
        self._generations.append(fut)
        self._authorize_event.set()

    def _clear_authorization(self) -> None:
        self._authorize_event.clear()

    async def _wait_for_authorization(self) -> None:
        await self._authorize_event.wait()

    async def _wait_for_generation(self, step_idx: int = -1) -> None:
        if not self._generations:
            raise RuntimeError("cannot use wait_for_generation: no active generation is running.")
        await asyncio.shield(self._generations[step_idx])

    async def _wait_for_scheduled(self) -> None:
        await asyncio.shield(self._scheduled_fut)

    def _mark_generation_done(self) -> None:
        if not self._generations:
            raise RuntimeError("cannot use mark_generation_done: no active generation is running.")
        with contextlib.suppress(asyncio.InvalidStateError):
            self._generations[-1].set_result(None)

    def _mark_done(self) -> None:
        self._is_speaking = False
        with contextlib.suppress(asyncio.InvalidStateError):
            self._done_fut.set_result(None)
            if self._generations:
                self._mark_generation_done()

    def _mark_scheduled(self) -> None:
        with contextlib.suppress(asyncio.InvalidStateError):
            self._scheduled_fut.set_result(None)


# --- AGENT SETUP ---
class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. Interact via voice. "
                "Keep responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or special characters. "
                "You are curious, friendly, and have a sense of humor. "
                "You will speak English to the user."
            )
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        logger.info(f"Looking up weather for {location}")
        return "sunny with a temperature of 70 degrees."


server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )

    IGNORED_WHILE_SPEAKING = {
        w.strip().lower()
        for w in os.getenv(
            "IGNORED_WORDS",
            "yeah,yes,ok,okay,hmm,uh-huh,right,uhm"
        ).split(",")
    }

    @session.on("user_input_transcribed")
    def _ignore_short_ack_while_speaking(ev):
        if not ev.is_final:
            return
        text = ev.text.strip().lower()
        words = text.split()
        if session.agent_state == "speaking" and len(words) < 2 and any(text.startswith(w) for w in IGNORED_WHILE_SPEAKING):
            logger.info(f"Ignoring filler during agent speech: {text}")
            session.clear_user_turn()
            return

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )

if __name__ == "__main__":
    cli.run_app(server)
