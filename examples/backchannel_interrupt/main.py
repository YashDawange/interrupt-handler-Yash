import logging
import asyncio
from dotenv import load_dotenv
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.plugins import silero, deepgram, elevenlabs, openai as lk_openai
from backchannel_logic import BackchannelAwareAgent, BackchannelConfig

load_dotenv()
logger = logging.getLogger("backchannel-agent")

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # Create the config
    backchannel_cfg = BackchannelConfig.from_env()
    
    # Initialize plugins
    # Note: Ensure DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, OPENAI_API_KEY are set in .env
    vad = ctx.proc.userdata["vad"]
    stt = deepgram.STT(model="nova-2") 
    llm = lk_openai.LLM(model="gpt-4o-mini")
    tts = elevenlabs.TTS() 

    # Create the custom agent
    agent = BackchannelAwareAgent(
        instructions="You are a helpful assistant. You listen to the user and answer questions.",
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        allow_interruptions=True,
        backchannel_config=backchannel_cfg,
    )

    session = AgentSession(
        vad=vad,
        stt=stt,
        llm=llm,
        tts=tts,
    )

    await session.start(
        agent=agent,
        room=ctx.room,
    )

if __name__ == "__main__":
    cli.run_app(server)
