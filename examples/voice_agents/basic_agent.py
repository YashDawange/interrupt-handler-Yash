import logging
import asyncio
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
from livekit.plugins import silero, openai
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("basic-agent")
load_dotenv()

# Hardcoded Ignore List
IGNORE_WORDS = ["yeah", "ok", "hmm", "right", "uh-huh", "sure", "okay"]

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. Interact via voice. Keep responses short. No emojis.",
        )

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    print(f"DEBUG: Agent Entrypoint Started for room {ctx.room.name}")

    # 1. Initialize LLM
    my_llm = openai.LLM(model="gpt-4o-mini")

    # 2. Configure Session
    session = AgentSession(
        stt="deepgram/nova-3",
        llm=None, # Manual Control
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.5,
    )

    is_agent_speaking = False

    @session.on("agent_speech_started")
    def on_agent_speech_started(ev):
        nonlocal is_agent_speaking
        is_agent_speaking = True
        print(">> STATUS: SPEAKING")

    @session.on("agent_speech_stopped")
    def on_agent_speech_stopped(ev):
        nonlocal is_agent_speaking
        is_agent_speaking = False
        print(">> STATUS: SILENT")

    # 3. Logic Layer
    async def _process_transcript(ev):
        try:
            if not ev.segment.final: return
            text = ev.segment.text.strip().lower()
            if not text: return
            
            print(f">> USER INPUT: '{text}'")

            # Check Ignore List
            user_words = [w.strip(".,!?") for w in text.split()]
            is_ignore = all(w in IGNORE_WORDS for w in user_words)

            # SCENARIO 1: Ignore
            if is_agent_speaking and is_ignore:
                print(f"   [ACTION]: IGNORING '{text}'")
                return

            # SCENARIO 2: Interrupt
            if is_agent_speaking and not is_ignore:
                print(f"   [ACTION]: INTERRUPTING for '{text}'")
                await session.interrupt()
            
            # SCENARIO 3: Reply
            print(f"   [ACTION]: REPLYING to '{text}'")
            session.chat_context.append(role="user", text=text)
            stream = my_llm.chat(chat_ctx=session.chat_context)
            await session.speak(stream)

        except Exception as e:
            print(f"CRITICAL ERROR in logic: {e}")

    @session.on("user_transcript")
    def on_user_transcript(ev):
        asyncio.create_task(_process_transcript(ev))

    # 4. START SESSION FIRST
    # We start the session immediately so audio tracks bind correctly
    print("DEBUG: Starting Session...")
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )
    print("DEBUG: Session Started. Audio should be live.")

    # 5. Send Greeting AFTER Session Start
    # This ensures we don't speak into the void
    async def safe_greeting():
        print(">> Waiting for audio path...")
        await asyncio.sleep(1) # Give 1s for tracks to settle
        print(">> Sending Greeting now...")
        try:
            greeting_stream = my_llm.chat(
                chat_ctx=session.chat_context,
                fnc_ctx=None
            )
            await session.speak(greeting_stream)
            print(">> GREETING SENT.")
        except Exception as e:
            print(f"Greeting failed: {e}")

    asyncio.create_task(safe_greeting())

if __name__ == "__main__":
    cli.run_app(server)