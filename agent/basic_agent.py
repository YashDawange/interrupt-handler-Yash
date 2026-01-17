from enum import Enum
import re
from dotenv import load_dotenv
load_dotenv()
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import deepgram, openai, silero, elevenlabs

from agent.interrupt_config import IGNORE_WORDS, INTERRUPT_WORDS


# ============================================================
# FSM STATES
# ============================================================
# Simple finite state machine to track what the agent is doing
class FSMState(str, Enum):
    SILENT = "SILENT"                 
    SPEAKING = "SPEAKING"             
    POTENTIAL_INTERRUPT = "POTENTIAL_INTERRUPT"
    

@function_tool
async def lookup_weather(context: RunContext, location: str):
    # Dummy tool just to show tool support
    return {"weather": "sunny", "temperature": 70}


# ============================================================
# TEXT PROCESSING LOGIC
# ============================================================
def tokenize(text: str) -> list[str]:
    """
    Converts raw transcript into clean lowercase tokens.

    Example:
    "Yeah, wait a second!" -> ["yeah", "wait", "a", "second"]
    """
    return re.findall(r"[a-zA-Z\-]+", text.lower())


def decide_interrupt(tokens: list[str]) -> str:
    """
    Decide whether the user actually wants to interrupt.

    Rules:
    1. If ANY interrupt keyword is present -> INTERRUPT
    2. If ONLY filler words are present -> IGNORE
    3. Anything else (mixed / unknown) -> INTERRUPT
    """

    # High priority: explicit interruption commands
    if any(word in INTERRUPT_WORDS for word in tokens):
        return "INTERRUPT"

    # Only backchanneling / filler words
    if tokens and all(word in IGNORE_WORDS for word in tokens):
        return "IGNORE"

    # Default safe behavior: interrupt
    return "INTERRUPT"


# ============================================================
# AGENT ENTRYPOINT
# ============================================================
async def entrypoint(ctx: JobContext):
    await ctx.connect()

    agent = Agent(
        instructions="You are a friendly voice assistant built by LiveKit.",
        tools=[lookup_weather],
    )

    # IMPORTANT:
    # allow_interruptions=False disables LiveKit's default behavior.
    # We manually control interruptions using our own logic.
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=elevenlabs.TTS(),
        allow_interruptions=False,  
    )

    fsm_state: FSMState = FSMState.SILENT
    session_running = False

    # ------------------------------------------------------------
    # EVENT: AGENT STATE CHANGED
    # ------------------------------------------------------------
    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        nonlocal fsm_state

        print(f"[AGENT_STATE] {ev.old_state} -> {ev.new_state}")

        if ev.new_state == "speaking":
            fsm_state = FSMState.SPEAKING
        else:
            fsm_state = FSMState.SILENT

        print(f"[FSM] current state = {fsm_state.value}")

    # ------------------------------------------------------------
    # EVENT: USER STATE CHANGED (VAD)
    # ------------------------------------------------------------
    @session.on("user_state_changed")
    def on_user_state_changed(ev):
        nonlocal fsm_state

        print(f"[USER_STATE] {ev.old_state} -> {ev.new_state}")

        # User started speaking while agent was speaking
        if ev.new_state == "speaking" and fsm_state == FSMState.SPEAKING:
            fsm_state = FSMState.POTENTIAL_INTERRUPT
            print("[FSM] SPEAKING -> POTENTIAL_INTERRUPT (VAD triggered)")

    # ------------------------------------------------------------
    # EVENT: USER TRANSCRIPT RECEIVED (STT)
    # ------------------------------------------------------------
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev):
        nonlocal fsm_state

        tokens = tokenize(ev.text)

        print(f"[STT] text='{ev.text}' tokens={tokens} final={ev.is_final}")
        print(f"[FSM] current state = {fsm_state.value}")

        # Only apply filtering if agent was speaking
        if fsm_state != FSMState.POTENTIAL_INTERRUPT:
            return

        decision = decide_interrupt(tokens)

        if decision == "IGNORE":
            # Backchannel detected -> continue speaking normally
            print("[DECISION] IGNORE filler (continue speaking)")
            fsm_state = FSMState.SPEAKING
            return

        # Anything else -> treat as real interruption
        print("[DECISION] INTERRUPT")

        if session_running:
            session.interrupt()

        fsm_state = FSMState.SILENT

    # ------------------------------------------------------------
    # START AGENT SESSION
    # ------------------------------------------------------------
    await session.start(agent=agent, room=ctx.room)
    session_running = True

    await session.generate_reply(
        instructions="Greet the user and ask about their day."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))