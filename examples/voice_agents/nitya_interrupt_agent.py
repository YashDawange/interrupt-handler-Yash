"""
Assignment: Gen-AI Real-Time Agent Logic
Author: Nitya Vettical

Description:
Implements state-aware interruption handling for conversational agents.
The agent behaves differently based on whether it is actively speaking:

- If speaking and user says filler words → ignore.
- If speaking and user says a meaningful command → interrupt speech.
- If silent and user says filler → treat as friendly acknowledgement.
- If silent and user gives real input → forward to LLM.

This file contains:
- Word lists for filler / interruption
- Internal agent state model
- Custom agent overriding LiveKit callbacks
"""

import logging
from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.plugins import cartesia, deepgram, openai, silero

logger = logging.getLogger("nitya-interrupt-agent")

load_dotenv()

# ----------------------------
# Configuration lists
# ----------------------------
IGNORE_LIST = ["yeah", "ok", "okay", "hmm", "uh-huh", "right"]
INTERRUPT_WORDS = ["wait", "stop", "no", "hold on", "pause"]

# ----------------------------
# State manager
# ----------------------------
class AgentState:
    def __init__(self):
        self.is_speaking = False
        self.pending_interruption = False


# ----------------------------
# Custom agent with interruption logic
# ----------------------------
class NityaInterruptAgent(Agent):
    def __init__(self, **kwargs):
        # Agent requires an "instructions" field – we add a default one here.
        kwargs.setdefault(
            "instructions",
            "You are a conversational assistant. Follow the interruption rules implemented by Nitya."
        )
        super().__init__(**kwargs)

        self.state = AgentState()

    # Called when TTS starts speaking
    async def on_tts_start(self, output):
        self.state.is_speaking = True

    # Called when TTS ends
    async def on_tts_end(self, output):
        self.state.is_speaking = False

    # Called for every STT transcript
    async def on_transcription(self, text, session: AgentSession):
        text = text.lower().strip()
        if not text:
            return

        contains_interrupt = any(word in text for word in INTERRUPT_WORDS)
        pure_ignore = text in IGNORE_LIST

        # -----------------------------------
        # CASE 1: Agent is speaking
        # -----------------------------------
        if self.state.is_speaking:

            if contains_interrupt:
                await session.interrupt_tts()
                await session.send_message("Okay, stopping.")
                return

            if pure_ignore:
                return

            # Ignore any other chatter while speaking
            return

        # -----------------------------------
        # CASE 2: Agent is silent
        # -----------------------------------
        if pure_ignore:
            await session.send_message("Great, let's continue.")
        else:
            # Forward normal user message to the LLM
            await session.provide_input(text)


# ----------------------------
# Server + entrypoint
# ----------------------------
server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):

    session = AgentSession(
        vad=silero.VAD.load(),
        llm=openai.LLM(model="gpt-4o-mini"),
        stt=deepgram.STT(),
        tts=cartesia.TTS(),
    )

    # Use the custom agent
    await session.start(
        agent=NityaInterruptAgent(),
        room="nitya-test-room"
    )

    await session.send_message("Hello! I am running and ready. You can talk to me now.")


# ----------------------------
# Standalone run hook
# ----------------------------
import asyncio

if __name__ == "__main__":
    asyncio.run(server.run())
