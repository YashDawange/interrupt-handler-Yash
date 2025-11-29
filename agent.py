import logging
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, openai, silero
from interruption_logic import InterruptionHandler

load_dotenv()

logger = logging.getLogger("interrupt-handler")
logic_handler = InterruptionHandler()

async def entrypoint(ctx: JobContext):
    await ctx.connect()


    agent = Agent(
        instructions=(
            "You are a history professor giving a lecture about the Roman Empire. "
            "Speak in short, clear sentences. "
            "Pause for exactly two seconds between every sentence. "
            "Example: 'The empire was vast.' 'It spanned three continents.'"
        )
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2"), 
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(),
        min_interruption_duration=10.0, 
    )

    @session.on("user_speech_committed")
    def on_user_speech(msg):
        user_text = msg.content
        is_speaking = session.response_audio_stream is not None
        
        # Consult the Logic Layer
        should_interrupt = logic_handler.should_interrupt(user_text, is_speaking)

        if is_speaking:
            if should_interrupt:
                logger.info(f"SEMANTIC INTERRUPT: '{user_text}' -> FORCE STOP.")
                async def force_stop():
                    # Sending an empty instruction flushes the buffer and stops audio.
                    await session.generate_reply(instructions="Stop speaking immediately.")
                ctx.create_task(force_stop())
                
            else:
                logger.info(f"PASSIVE INPUT: '{user_text}' -> IGNORED.")
                msg.cancel()

    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(instructions="Start the lecture now.")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))