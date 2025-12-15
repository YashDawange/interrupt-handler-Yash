import logging
import string
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
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("basic-agent")

load_dotenv()
# Words to ignore if spoken by the user during agent response
IGNORE_WORDS = {
    "yeah", "ok", "okay", "hmm", "aha", "uhhuh", "right", 
    "yes", "yep", "sure", "got it"
}

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice."
            "with that in mind keep your responses concise and to the point."
            "do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "you will speak english to the user",
        )

    async def on_enter(self):
        # Generate the initial greeting when the agent joins
        self.session.generate_reply()

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # Log the room name
    ctx.log_context_fields = {"room": ctx.room.name}
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        
        resume_false_interruption=True, 
        # Give us a 1-second buffer to check the text before cutting off the stream permanently
        false_interruption_timeout=1.0, 
    )

    # Metrics Setup
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)
    @session.on("user_speech_committed")
    def on_user_speech_committed(msg):
        transcript = msg.transcript if hasattr(msg, "transcript") else str(msg)

        text_clean = transcript.strip().lower()
        text_clean = text_clean.replace('.', '')
        text_clean = text_clean.replace(',', '')
        text_clean = text_clean.replace('!', '')
        text_clean = text_clean.replace('?', '')
        

        is_speaking = session.current_agent_item is not None
        
        print(f"\n[LOGIC CHECK] Input: '{text_clean}' | Speaking: {is_speaking}")
        if text_clean in IGNORE_WORDS:
            if is_speaking:
                print(f"[LOGIC RESULT] MATCHED & IGNORED. (Blocking Reply)")
            
                # We remove the last user message to prevent LLM confusion.
                if session.chat_ctx.messages:
                    session.chat_ctx.messages.pop()
                return
            else:
                print(f"[LOGIC RESULT] PASSIVE ANSWER. (Letting LLM Respond)")
        else:
            print(f"[LOGIC RESULT] VALID INTERRUPTION. (Letting LLM Respond)")


    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )

if __name__ == "__main__":
    cli.run_app(server)