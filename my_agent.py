# agent.py
# FINAL VERSION – includes:
# - Filler blocking even when agent is silent
# - Urgent interrupt detection even on partial STT
# - Custom greeting handler
# - Short atomic responses only (never fragments)
# - Smooth TTS via preemptive_generation
# - No unsupported kwargs

import logging
import time
import asyncio
import traceback
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
)

from livekit.plugins import deepgram, silero
from logic import should_interrupt, IGNORE_WORDS, IGNORE_PHRASES, URGENT_COMMANDS

load_dotenv()

logger = logging.getLogger("my-agent")
logger.setLevel(logging.INFO)


class ConversationState:
    def _init_(self):
        self.is_speaking = False
        self.last_vad_trigger = 0.0
        self.false_start_window = 0.5

    def mark_speaking(self):
        self.is_speaking = True

    def mark_silent(self):
        self.is_speaking = False

    def register_vad_trigger(self):
        self.last_vad_trigger = time.time()

    def is_within_false_start_window(self):
        return (time.time() - self.last_vad_trigger) < self.false_start_window


class SmartInterruptAgent(Agent):
    def _init_(self, instructions: str):
        # Force short atomic statements — no long explanations
        instructions = (
            instructions
            + "\nAlways speak in short complete sentences, 1–2 lines max.\n"
            + "Never continue a broken sentence.\n"
            + "Never ask questions unless the user explicitly asks something.\n"
            + "Do not ask 'Is there more?' or similar follow-ups.\n"
        )
        super()._init_(instructions=instructions)
        self.state = ConversationState()

    async def on_tts_play(self, event):
        self.state.mark_speaking()

    async def on_tts_stop(self, event):
        self.state.mark_silent()

    async def on_vad_start(self, event):
        self.state.register_vad_trigger()

    async def on_stt_update(self, event):
        user_text = (event.text or "").strip()
        if not user_text:
            return

        print(f"[USER SAID]: {user_text}")

        # Try reading final/partial info
        is_final = getattr(event, "is_final", None)
        if is_final is None:
            is_final = True

        # Normalized version for matching
        cleaned = user_text.lower().strip()

        # -----------------------------
        # PARTIAL STT UPDATE HANDLING
        # -----------------------------
        if not is_final:
            # Check if partial contains urgent keyword
            tokens = cleaned.replace("-", "").split()
            if any(w in URGENT_COMMANDS for w in tokens):
                print(" -> PARTIAL INTERRUPT due to urgent word")
                event.interrupt = True
                return

            print(" -> IGNORE partial STT")
            return

        # -----------------------------
        # CUSTOM GREETING HANDLER
        # -----------------------------
        greetings = {"hello", "hello?", "hi", "hey", "yo", "hi there"}
        if cleaned in greetings and not self.state.is_speaking:
            print(" -> Greeting detected.")
            await self.session.say("Hi, I’m here. How can I help?")
            event.interrupt = False
            return

        # =====================================================================
        # CASE 1: AGENT IS SILENT → treat meaningful input as real, ignore filler
        # =====================================================================
        if not self.state.is_speaking:
            # If filler even while silent → ignore
            if (
                len(cleaned) <= 4
                or cleaned in IGNORE_WORDS
                or cleaned in IGNORE_PHRASES
            ):
                print(f" -> IGNORE filler while silent: '{user_text}'")
                event.interrupt = False
                return

            # Otherwise treat as real input
            print(f" -> ACCEPT real input while silent: '{user_text}'")
            event.interrupt = True
            return

        # =====================================================================
        # CASE 2: AGENT IS SPEAKING → check full logic (interrupt / ignore)
        # =====================================================================
        if should_interrupt(cleaned):
            print(f" -> INTERRUPT: '{user_text}'")
            event.interrupt = True
        else:
            print(f" -> IGNORE filler while speaking: '{user_text}'")
            event.interrupt = False


async def entrypoint(ctx: JobContext):
    print(">>> STARTING AGENT")
    try:
        await ctx.connect()
        print(f">>> Connected to room {ctx.room.name}")

        agent = SmartInterruptAgent(
            "You are a concise assistant who responds clearly and briefly."
        )

        # No unsupported kwargs.
        # preemptive_generation improves speaking flow & prevents choppiness.
        session = AgentSession(
            stt=deepgram.STT(),
            llm="google/gemini-2.0-flash",
            tts=deepgram.TTS(),
            vad=silero.VAD.load(),
            preemptive_generation=True,
        )

        await session.start(room=ctx.room, agent=agent)

        await session.say(
            "Hello! I am ready. My voice and interruption behavior are optimized. What would you like to do?"
        )

        print("[SYSTEM] Agent running.")
        await asyncio.Event().wait()

    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()


if _name_ == "_main_":
    agents.cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))