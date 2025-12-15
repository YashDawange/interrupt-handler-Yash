import asyncio
import logging
import os
from dotenv import load_dotenv

# Import standard LiveKit tools
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    stt, # Needed to create fake audio events
)
from livekit.plugins import deepgram, openai, silero
from livekit import rtc

# Import your local classes
from voice.agent import Agent
from voice.agent_session import AgentSession

load_dotenv()
logger = logging.getLogger("assignment-runner")

async def entrypoint(ctx: JobContext):
    # 1. Connect
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # 2. Setup Agent & Session
    agent = Agent(instructions="You are a helpful assistant. If asked, tell a very long story.")
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=openai.LLM(
            model="llama-3.3-70b-versatile", 
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY")
        ),
        tts=deepgram.TTS(),
    )

    # 3. Start the Agent
    await session.start(agent, room=ctx.room)

    # --- 🌉 THE BRIDGE: Connect Text Chat to Your Audio Logic ---
    # This block listens for text from 'generate_proof.py' and tricks
    # the agent into thinking it was spoken audio.
    
    chat = rtc.ChatManager(ctx.room)

    async def on_chat_message(msg: rtc.ChatMessage):
        text = msg.message
        logger.info(f"📩 Received Text Command: '{text}'")

        # Create a "Fake" Audio Event containing this text
        fake_event = stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(text=text, confidence=1.0)]
        )

        # Feed it into your EXISTING logic in agent_activity.py
        if session._activity:
            session._activity.on_final_transcript(fake_event)

    # Listen for messages
    chat.on("message_received", on_chat_message)
    # -----------------------------------------------------------

    # Greet
    await session.generate_reply(instructions="Say hello and wait for the test.")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))