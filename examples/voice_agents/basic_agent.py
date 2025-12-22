import logging
import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this script
load_dotenv(Path(__file__).parent / ".env")

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
from livekit.agents.stt import SpeechEventType
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import the interruption filter functions
from interruption_filter import should_interrupt_agent, should_interrupt_optimistic

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")



class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You interact with users via voice. "
            "Keep responses concise and to the point. "
            "Do not use emojis, asterisks, markdown, or other special characters in your responses. "
            "You are curious and friendly, and have a sense of humor. "
            "You will speak English to the user.",
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

    # Smart Interruption Logic
    async def stt_node(self, audio, model_settings):
        """
        Override the Speech-to-Text node to intercept and filter user speech.
        
        This allows us to:
        - Ignore passive backchanneling (yeah, uh-huh, okay) while agent is speaking
        - Immediately react to active commands (stop, wait, no)
        - Prevent UI flickering from start_of_speech events during agent speech
        """
        async for event in Agent.default.stt_node(self, audio, model_settings):
            is_speaking = self.session.agent_state == "speaking"

            # FAST PATH (Interim Results)
            # React instantly while user is still speaking (e.g., "Sto...")
            if event.type == SpeechEventType.INTERIM_TRANSCRIPT:
                if event.alternatives and event.alternatives[0].text:
                    partial_text = event.alternatives[0].text
                    
                    # If we detect a command NOW, interrupt immediately
                    if is_speaking and should_interrupt_optimistic(partial_text):
                        logger.info(f"⚡ FAST INTERRUPT: Heard partial '{partial_text}'")
                        self.session.interrupt()
                
                yield event

            # ACCURATE PATH (Final Transcript)
            # React when user finishes a sentence
            elif event.type == SpeechEventType.FINAL_TRANSCRIPT:
                if event.alternatives and event.alternatives[0].text:
                    text = event.alternatives[0].text
                    
                    # Use robust logic to decide
                    should_stop = should_interrupt_agent(text, is_speaking)

                    if should_stop:
                        # It was a command (or normal speech)
                        if is_speaking:
                            logger.info(f"🛑 FINAL INTERRUPT: Heard '{text}'")
                            self.session.interrupt()
                        yield event
                    else:
                        # It was passive (e.g., "Yeah") -> We SWALLOW this event.
                        # The LLM never sees it. The Agent keeps talking seamlessly.
                        logger.info(f"🔇 IGNORING BACKCHANNEL: '{text}'")
                        continue
                else:
                    yield event

            # SUPPRESS START_OF_SPEECH while agent is speaking
            # Hide "Start of Speech" if we are speaking to prevent UI flickering
            elif event.type == SpeechEventType.START_OF_SPEECH:
                if is_speaking:
                    # Don't yield - suppress this event while agent is speaking
                    continue
                yield event
            
            else:
                yield event

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
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt="deepgram/nova-3",
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm="openai/gpt-4o-mini",
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        
        # --- SMART INTERRUPTION CONFIGURATION ---
        # Allow interruptions so the agent can react to user speech
        allow_interruptions=True,
        # Resume speaking if the interruption was likely a false positive
        resume_false_interruption=True,
        false_interruption_timeout=1.5,  # seconds to wait before resuming
        # Require at least 2 words to trigger an interruption (filters "yeah", "ok", etc.)
        min_interruption_words=2,
    )

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # uncomment to enable the Krisp BVC noise cancellation
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)