# import logging

# from dotenv import load_dotenv

# from livekit.agents import (
#     Agent,
#     AgentServer,
#     AgentSession,
#     JobContext,
#     JobProcess,
#     MetricsCollectedEvent,
#     RunContext,
#     cli,
#     metrics,
#     room_io,
# )
# from livekit.agents.llm import function_tool
# from livekit.plugins import silero
# from livekit.plugins.turn_detector.multilingual import MultilingualModel

# # uncomment to enable Krisp background voice/noise cancellation
# # from livekit.plugins import noise_cancellation

# logger = logging.getLogger("basic-agent")

# load_dotenv()


# class MyAgent(Agent):
#     def __init__(self) -> None:
#         super().__init__(
#             instructions="Your name is Kelly. You would interact with users via voice."
#             "with that in mind keep your responses concise and to the point."
#             "do not use emojis, asterisks, markdown, or other special characters in your responses."
#             "You are curious and friendly, and have a sense of humor."
#             "you will speak english to the user",
#         )

#     async def on_enter(self):
#         # when the agent is added to the session, it'll generate a reply
#         # according to its instructions
#         self.session.generate_reply()

#     # all functions annotated with @function_tool will be passed to the LLM when this
#     # agent is active
#     @function_tool
#     async def lookup_weather(
#         self, context: RunContext, location: str, latitude: str, longitude: str
#     ):
#         """Called when the user asks for weather related information.
#         Ensure the user's location (city or region) is provided.
#         When given a location, please estimate the latitude and longitude of the location and
#         do not ask the user for them.

#         Args:
#             location: The location they are asking for
#             latitude: The latitude of the location, do not ask user for it
#             longitude: The longitude of the location, do not ask user for it
#         """

#         logger.info(f"Looking up weather for {location}")

#         return "sunny with a temperature of 70 degrees."


# server = AgentServer()


# def prewarm(proc: JobProcess):
#     proc.userdata["vad"] = silero.VAD.load()


# server.setup_fnc = prewarm


# @server.rtc_session()
# async def entrypoint(ctx: JobContext):
#     # each log entry will include these fields
#     ctx.log_context_fields = {
#         "room": ctx.room.name,
#     }
#     session = AgentSession(
#         # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
#         # See all available models at https://docs.livekit.io/agents/models/stt/
        
#         stt="deepgram/nova-3",

#         # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
#         # See all available models at https://docs.livekit.io/agents/models/llm/
#         llm="openai/gpt-4.1-mini",
#         # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
#         # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
#         tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
#         # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
#         # See more at https://docs.livekit.io/agents/build/turns
        
#         turn_detection=MultilingualModel(),
#         vad=ctx.proc.userdata["vad"],
#         #   turn_detection="stt",
#         #   vad=ctx.proc.userdata["vad"],

#         # allow the LLM to generate a response while waiting for the end of turn
#         # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
#         preemptive_generation=True,
#         # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
#         # when it's detected, you may resume the agent's speech
#         resume_false_interruption=True,
#         false_interruption_timeout=1.0,
#         # min_interruption_words=1,
#     )

#     # log metrics as they are emitted, and total usage after session is over
#     usage_collector = metrics.UsageCollector()

#     @session.on("user_input_transcribed")
#     def on_transcript(ev):
#         print(f"TRANSCRIPT_DEBUG: '{ev.transcript}' (final={ev.is_final})")


#     @session.on("metrics_collected")
#     def _on_metrics_collected(ev: MetricsCollectedEvent):
#         metrics.log_metrics(ev.metrics)
#         usage_collector.collect(ev.metrics)

#     async def log_usage():
#         summary = usage_collector.get_summary()
#         logger.info(f"Usage: {summary}")

#     # shutdown callbacks are triggered when the session is over
#     ctx.add_shutdown_callback(log_usage)

#     await session.start(
#         agent=MyAgent(),
#         room=ctx.room,
#         room_options=room_io.RoomOptions(
#             audio_input=room_io.AudioInputOptions(
#                 # uncomment to enable the Krisp BVC noise cancellation
#                 # noise_cancellation=noise_cancellation.BVC(),
#             ),
#         ),
#     )


# if __name__ == "__main__":
#     cli.run_app(server)

import logging
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
    inference,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("basic-agent")

load_dotenv()

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are Kelly, a friendly voice assistant. Speak briefly and clearly."
        )
        self._last_speaking_time = 0

    async def on_enter(self):
        self.session.generate_reply()

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    print("\n" + "="*60)
    print("INTELLIGENT INTERRUPTION HANDLER - ASSIGNMENT MODE")
    print("="*60)
    print("Filler words (yeah, okay, right, hmm, aha) -> IGNORED when agent speaks")
    print("Interrupt commands (stop, wait, hold on, no) -> IMMEDIATE INTERRUPT")
    print("Same words when agent silent -> NORMAL RESPONSE")
    print("="*60 + "\n")
    
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(model="cartesia/sonic-2"),
        turn_detection="stt",  # Use STT for better accuracy
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.2,  # Gives STT time to catch up
        min_interruption_words=2,  # Need 2+ words to interrupt (helps with fillers)
        min_interruption_duration=0.4,  # Ignore very brief sounds
        allow_interruptions=True,
    )

    @session.on("user_input_transcribed")
    def on_transcript(ev):
        print(f"[USER] {ev.transcript} (final={ev.is_final})")

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            close_on_disconnect=False
        ),
    )

if __name__ == "__main__":
    cli.run_app(server)