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

# [MODIFIED] Import the configurable ignore list logic
from config import get_ignore_words

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

load_dotenv()


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
        # [MODIFIED] We handle the greeting manually in entrypoint now
        # to ensure it uses our manual LLM instance.
        pass

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        Ensure the user's location (city or region) is provided.
        When given a location, please estimate the latitude and longitude of the location and
        do not ask the user for them.

        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # [MODIFIED] Load the Ignore List at startup
    ignore_words = get_ignore_words()

    # [MODIFIED] Initialize LLM manually so we can control WHEN it generates text
    my_llm = openai.LLM(model="gpt-4.1-mini")

    session = AgentSession(
        stt="deepgram/nova-3",
        # [CRITICAL FIX] Disable auto-pilot. We will trigger the LLM manually.
        llm=None, 
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        # This ensures that if we decide to IGNORE the input, the audio resumes
        resume_false_interruption=True, 
        false_interruption_timeout=1.5, 
    )

    # State Tracking
    is_agent_speaking = False

    @session.on("agent_speech_started")
    def on_agent_speech_started(ev):
        nonlocal is_agent_speaking
        is_agent_speaking = True
        logger.info("Agent State: SPEAKING")

    @session.on("agent_speech_stopped")
    def on_agent_speech_stopped(ev):
        nonlocal is_agent_speaking
        is_agent_speaking = False
        logger.info("Agent State: SILENT")

    # [FIXED] Asynchronous Logic Helper
    # This handles the Matrix Logic and manually replies
    async def _handle_transcript_logic(ev):
        nonlocal is_agent_speaking
        
        if not ev.segment.final:
            return

        text = ev.segment.text.strip().lower()
        if not text:
            return

        user_words = [w.strip(".,!?") for w in text.split()]
        is_ignore_content = all(w in ignore_words for w in user_words)

        logger.info(f"Analyzed Input: '{text}' | Ignore: {is_ignore_content} | Speaking: {is_agent_speaking}")

        # SCENARIO 1: Agent is Speaking + "Yeah/Ok" -> IGNORE
        if is_agent_speaking and is_ignore_content:
            logger.info(f"ACTION: IGNORING '{text}' - Resuming playback...")
            # By returning here and NOT calling speak(), the session will
            # automatically resume the previous audio (thanks to resume_false_interruption)
            return

        # SCENARIO 2: Agent is Speaking + "Stop/Wait" -> INTERRUPT
        if is_agent_speaking and not is_ignore_content:
            logger.info(f"ACTION: INTERRUPTING for command '{text}'")
            await session.interrupt()
            # Logic continues below to generate a reply...

        # SCENARIO 3: Agent is Silent + "Yeah" -> RESPOND (Normal Turn)
        # Logic continues below to generate a reply...

        # --- MANUAL REPLY GENERATION ---
        # 1. Add user text to memory
        session.chat_context.append(role="user", text=text)
        
        # 2. Generate response using our manual LLM
        stream = my_llm.chat(chat_ctx=session.chat_context)
        
        # 3. Speak the response
        await session.speak(stream)

    # [FIXED] Synchronous Event Listener
    @session.on("user_transcript")
    def on_user_transcript(ev):
        asyncio.create_task(_handle_transcript_logic(ev))

    # [ADDED] Manual Initial Greeting
    # Since we disabled auto-LLM, we must manually trigger the first "Hello"
    @session.on("room_connected")
    def on_room_connected(ev):
        async def send_greeting():
            # Wait a moment for connection to stabilize
            await asyncio.sleep(1)
            # Use the instructions from MyAgent to generate the first hello
            # (The session context is initialized with MyAgent instructions automatically)
            greeting_stream = my_llm.chat(chat_ctx=session.chat_context)
            await session.speak(greeting_stream)
        
        asyncio.create_task(send_greeting())

    # log metrics as they are emitted
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)