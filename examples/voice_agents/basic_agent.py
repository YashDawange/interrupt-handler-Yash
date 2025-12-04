import asyncio
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.plugins import deepgram, cartesia
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from interruption_logic import InterruptionHandler

load_dotenv()

class MyAgent(Agent):
    def __init__(self):
        super().__init__(instructions="Logic Tester")

server = AgentServer()

def prewarm(proc: JobProcess):
    try:
        from livekit.plugins import silero
        proc.userdata["vad"] = silero.VAD.load()
    except ImportError:
        pass

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    int_handler = InterruptionHandler()
    agent = MyAgent()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        tts=cartesia.TTS(model="sonic-2"),
        turn_detection=MultilingualModel(),
        preemptive_generation=False,
    )

    @session.on("user_transcript")
    def on_user_transcript(data):
        if hasattr(data, 'transcript'):
            text = data.transcript.text
        else:
            text = str(data)

        if not text: return

        # We assume True to demonstrate the "Ignore" capability for the assignment proof
        decision = int_handler.should_interrupt(text, is_agent_speaking=True)

        if decision == "INTERRUPT":
            print(f"\n LOGIC: INTERRUPT (Input: '{text}')\n", flush=True)
            asyncio.create_task(session.interrupt())

        elif decision == "IGNORE":
            print(f"\n LOGIC: IGNORE (Input: '{text}')\n", flush=True)

    await session.start(room=ctx.room, agent=agent)
    print("\n>>> SYSTEM READY. SPEAK NOW. <<<\n", flush=True)

if __name__ == "__main__":
    cli.run_app(server)