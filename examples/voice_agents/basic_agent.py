import logging
from pathlib import Path
from dotenv import load_dotenv

from livekit.agents import (
    Agent, AgentServer, AgentSession, JobContext, JobProcess, cli, metrics
)
from livekit.agents.stt import SpeechEventType
from livekit.plugins import silero, deepgram, openai, cartesia
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Custom logic imports
from interruption_filter import validate_interruption, is_priority_command

load_dotenv(Path(__file__).parent / ".env")
logger = logging.getLogger("voice-agent")

class KellyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="Your name is Kelly. Be professional but witty. Keep answers short.",
        )

    async def on_enter(self):
        # Greets user when the session starts
        self.session.generate_reply()

    async def stt_node(self, audio, model_settings):
        """Custom speech node to handle smart interruptions."""
        async for event in Agent.default.stt_node(self, audio, model_settings):
            speaking = self.session.agent_state == "speaking"

            if event.type == SpeechEventType.INTERIM_TRANSCRIPT:
                # Fast-path for 'Stop' commands
                text = event.alternatives[0].text
                if speaking and is_priority_command(text):
                    logger.info(f"Priority Interrupt: {text}")
                    self.session.interrupt()
                yield event

            elif event.type == SpeechEventType.FINAL_TRANSCRIPT:
                text = event.alternatives[0].text
                if validate_interruption(text, speaking):
                    if speaking:
                        logger.info(f"Final Interrupt: {text}")
                        self.session.interrupt()
                    yield event
                else:
                    logger.info(f"Ignored Backchannel: {text}")
                    continue # Drop the event; agent keeps talking

            elif event.type == SpeechEventType.START_OF_SPEECH:
                # Prevent UI flickering while agent is already talking
                if speaking:
                    continue
                yield event
            else:
                yield event

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server = AgentServer()
server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(),
        tts=cartesia.TTS(),
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
        allow_interruptions=True,
        # Ensure 1-word commands like 'Stop' work despite word count
        min_interruption_words=1, 
    )
    await session.start(agent=KellyAgent(), room=ctx.room)

if __name__ == "__main__":
    cli.run_app(server)