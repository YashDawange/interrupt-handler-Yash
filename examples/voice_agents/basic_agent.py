import logging
from dotenv import load_dotenv,find_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, JobProcess, cli
from livekit.plugins import groq, deepgram, silero 
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv(find_dotenv())
logger = logging.getLogger("basic-agent")
IGNORE_WORDS = ["yeah", "ok", "hmm", "right", "uh-huh", "got it"]


# 1. Initialize the server without constructor arguments
server = AgentServer()

def prewarm(proc: JobProcess):
    # Preload VAD for faster startup
    proc.userdata["vad"] = silero.VAD.load()

# 2. Assign the prewarm function directly to the server attribute
server.setup_fnc = prewarm

# 3. Use the decorator to register your entrypoint
@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # IMPORTANT: Connect to the room first
    await ctx.connect()

    session = AgentSession(
        stt=deepgram.STT(),
        llm=groq.LLM(model="llama-3.1-8b-instant"), 
        # Correctly using Cartesia TTS
        tts=deepgram.TTS(
            model="aura-luna-en", # Example: use a valid Deepgram model like 'aura-luna-en' or 'aura-asteria-en'
        ), 
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
        min_interruption_words=2, 
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
    )

    # Use the Agent class (Kelly)
    agent = Agent(instructions="Your name is Kelly. Be concise and friendly.")
    
    await session.start(agent=agent, room=ctx.room)
    await session.say("Hi, I'm Kelly. How can I help you today?")

if __name__ == "__main__":
    cli.run_app(server)