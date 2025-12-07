
import logging
import os
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
)
from livekit.plugins import silero, google, deepgram, openai
from livekit.agents.voice.interrupt_handler import InterruptHandler, AgentState


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("intelligent-agent-refactor")

load_dotenv()


def warm_vad(job_proc: JobProcess) -> None:
    """Load the VAD model once so audio startup is faster."""
    job_proc.userdata["vad"] = silero.VAD.load()
    logger.info("✓ VAD warmed and ready")


async def start_job(context: JobContext) -> None:
    """Main job entrypoint used by the worker runner."""
    logger.info(f" Launching session for room: {context.room.name}")

    
    await context.connect()


    assistant = Agent(
        instructions=(
            "You are a helpful AI assistant.\n\n"
            "INTERRUPTION RULES:\n"
            "- When the user says 'stop', 'wait', or 'hold on', stop speaking immediately and "
            "acknowledge with a single short word like 'Okay' or 'Stopped'. Do NOT explain that "
            "you are stopping.\n"
            "- If interrupted with a direct question, answer it concisely.\n"
            "- Keep replies natural and conversational; when interrupted keep them brief."
        )
    )

   
    interrupter = InterruptHandler()
    speaker_state = AgentState.SILENT


    agent_session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en-US", interim_results=True),
        llm=openai.LLM(
            model="llama-3.1-8b-instant",
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.7,
        ),
        tts=deepgram.TTS(model="aura-asteria-en"),
        vad=context.proc.userdata["vad"],
        allow_interruptions=True,
        min_interruption_words=5,  
        min_interruption_duration=0.0,
    )

    retry_interrupt_check = False

    @agent_session.on("agent_state_changed")
    def _handle_agent_state_change(evt):
        """Observe when the assistant starts/stops speaking."""
        nonlocal speaker_state, retry_interrupt_check
        if evt.new_state == "speaking":
            speaker_state = AgentState.SPEAKING
            retry_interrupt_check = False
            logger.info(" Assistant began speaking")
        elif evt.old_state == "speaking":
            speaker_state = AgentState.SILENT
            logger.info(" Assistant finished speaking")

    @agent_session.on("user_input_transcribed")
    def _on_transcript(evt):


        """Watch STT transcripts and decide whether to manually trigger an interrupt."""
        nonlocal retry_interrupt_check

        text = (evt.transcript or "").lower().strip()
        if not text:
            return

        # Handle interim transcripts while the assistant is speaking:
        if not evt.is_final and speaker_state == AgentState.SPEAKING:
            logger.info(f" Interim transcript: '{text}'")

            should_interrupt = interrupter.should_interrupt(speaker_state, text)

            if should_interrupt:
                # Attempt to interrupt the TTS immediately.
                logger.info(f" Triggering manual interrupt for interim: '{text}'")
                try:
                    agent_session.interrupt()
                except Exception as exc:
                    logger.warning(f"Manual interrupt failed: {exc}")
            else:
                # Avoid noisy logs for filler words
                if interrupter._tokenize(text):
                    pass

        # User finished speaking
        elif evt.is_final:
            logger.info(f" Final transcript: '{text}'")
            should_interrupt = interrupter.should_interrupt(speaker_state, text)

            if should_interrupt:
                logger.info(f" Triggering manual interrupt for final: '{text}'")
                try:
                    agent_session.interrupt()
                except Exception as exc:
                    logger.warning(f"Manual interrupt (final) failed: {exc}")
            else:
                logger.info(" Treated as filler/ignored while speaking")

    # start session and greet the user
    await agent_session.start(agent=assistant, room=context.room)
    await agent_session.say("Hello! I'm your AI assistant. Go ahead, ask me anything!")

    logger.info(" Session is live and ready")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=start_job,
            prewarm_fnc=warm_vad,
            agent_name="friendly-interrupt-agent",
        )
    )