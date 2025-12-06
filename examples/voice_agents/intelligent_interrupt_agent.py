# intelligent_interrupt_agent.py
# Author: Abhay Kumar

import logging
import os
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AgentStateChangedEvent,
    JobContext,
    JobProcess,
    UserInputTranscribedEvent,
    cli,
)
from livekit.agents import room_io
from livekit.plugins import (
    cartesia,
    openai,
    silero,
    deepgram
)

from interrupt_handler import InterruptHandler


logger = logging.getLogger("intelligent-interrupt-agent")
logger.setLevel(logging.INFO)

load_dotenv()
print("DEBUG LIVEKIT URL:", os.getenv("LIVEKIT_URL"))

server = AgentServer()



# Speaking state tracker

class AgentSpeakingState:
    def __init__(self) -> None:
        self.state = "idle"

    @property
    def is_speaking(self) -> bool:
        return self.state == "speaking"

    @property
    def is_silent(self) -> bool:
        return self.state in {"thinking", "listening", "idle"}


# Prewarm VAD once per worker

def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm


# Main Logic

@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:

    ctx.log_context_fields = {"room": ctx.room.name}

    interrupt_handler = InterruptHandler()
    speaking_state = AgentSpeakingState()

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],

        # STT
        stt=deepgram.STT(api_key=os.getenv("DEEPGRAM_API_KEY")),

        # LLM (OpenRouter-friendly)
        llm=openai.LLM(
            model=os.getenv("OPENAI_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        ),

        # TTS
        tts=cartesia.TTS(api_key=os.getenv("CARTESIA_API_KEY")),

        allow_interruptions=False,
        false_interruption_timeout=None,
        min_interruption_duration=0.15,
        min_interruption_words=1,
    )

    # Track speaking state
    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        speaking_state.state = ev.new_state
        logger.info(f"Agent state changed: {ev.old_state} → {ev.new_state}")

    # STT transcript handler with interruption logic
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:

        if not ev.is_final:
            return

        transcript = (ev.transcript or "").strip()
        if not transcript:
            return

        print("USER SAID:", transcript)
        logger.info(f"[STT FINAL] speaking={speaking_state.is_speaking} | text={transcript!r}")

        if speaking_state.is_speaking:
            decision = interrupt_handler.classify(transcript)

            if decision == "IGNORE":
                logger.info(f"IGNORE filler: {transcript!r}")
                return

            if decision == "INTERRUPT":
                logger.info(f"INTERRUPT detected: {transcript!r}")
                session.interrupt()
                return

            logger.info(f"NORMAL interruption: {transcript!r}")
            session.interrupt()
            return

        logger.info(f"Agent silent → message passed to LLM: {transcript!r}")

    # Start the session & greet
    await session.start(
        agent=Agent(
            instructions=(
                "You are a helpful voice assistant. "
                "Keep responses under 2 short sentences. "
                "Speak slowly and leave small pauses so the user can interrupt. "
                "If the user says stop, wait, or no — stop immediately. "
                "Do not speak long monologues. "
                "Always allow the user to talk after every sentence."
            )
        ),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            text_output=True,
            audio_output=True,
        ),
    )

    session.generate_reply(
        instructions="Greet the user and start explaining something briefly."
    )


# Main runner

if __name__ == "__main__":
    cli.run_app(server)
