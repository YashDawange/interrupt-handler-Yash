import logging
from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.plugins import deepgram, openai, silero

logger = logging.getLogger("my-submission")
load_dotenv()

# 1. Define the words to IGNORE (The "Soft" inputs)
IGNORE_WORDS = {"yeah", "ok", "okay", "hm", "hmm", "uh-huh", "right", "correct", "yep"}

class MyAgent(Agent):
    def __init__(self):
        super().__init__(
            # FIX 1: PROMPT ENGINEERING
            # We explicitly tell the AI to ignore backchanneling.
            instructions=(
                "You are a helpful assistant. You are currently being tested on interruption handling. "
                "Read a long sentence about history to test me. "
                "IMPORTANT: If the user says 'yeah', 'ok', 'uh-huh', or 'hmm' while you are speaking, "
                "DO NOT STOP. DO NOT acknowledge it. DO NOT ask if they want you to stop. "
                "Just keep reading your text seamlessly."
            ),
        )

    async def on_enter(self):
        # Trigger the agent to speak immediately upon joining
        self.session.generate_reply()

server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # 2. Initialize the Session
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(language="en"), 
        llm=openai.LLM(),
        tts=openai.TTS(),
    )

    # 3. THE LOGIC LAYER
    @session.on("user_speech_committed")
    def on_user_speech(msg):
        # Handle message content safely
        if hasattr(msg, 'content'):
            user_text = msg.content
        else:
            user_text = str(msg)

        clean_text = user_text.lower().strip(".,!?")
        logger.info(f"User said: {clean_text}")

        # CHECK: Is the agent currently speaking?
        is_agent_speaking = session.agent.is_speaking

        # LOGIC A: If text is in IGNORE list
        if clean_text in IGNORE_WORDS:
            logger.info(f" -> IGNORING passive input: '{clean_text}'")
            # If the agent is speaking, we do absolutely nothing.
            # The Prompt Instructions (above) handle the rest by telling the LLM to ignore it.
            return 
        
        # LOGIC B: If it is a REAL command (like "Stop") AND agent is speaking
        if is_agent_speaking:
            logger.info(f" -> INTERRUPTING for command: '{clean_text}'")
            session.agent.interrupt() 
            session.generate_reply() # Force a new response for the command

    # 4. Start the session with Interruption disabled
    # We try multiple ways to disable the default "Auto-Kill" switch
    # depending on which version of the library you have.
    try:
        # Try Option A: Standard for newer versions
        await session.start(agent=MyAgent(), room=ctx.room, allow_interruptions=False)
    except TypeError:
        try:
            # Try Option B: Older versions
            await session.start(agent=MyAgent(), room=ctx.room, interrupt_speech_on_input=False)
        except TypeError:
            # Fallback: Just start it (The prompt engineering will do the heavy lifting)
            logger.warning("Could not set interrupt flag. Relying on Logic Layer.")
            await session.start(agent=MyAgent(), room=ctx.room)

if __name__ == "__main__":
    cli.run_app(server)