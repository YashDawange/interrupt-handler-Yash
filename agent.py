from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import the interruption handler
from interruption_handler import install_interruption_handler

# Load env variables from .env.local
load_dotenv(".env.local")


# -----------------------------------------------------------
# Simple assistant agent
# -----------------------------------------------------------
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a friendly, helpful voice AI assistant. 
Keep responses short, clear, and natural.
Avoid emojis and fancy formatting.
""",
        )


# -----------------------------------------------------------
# Create the AgentServer
# -----------------------------------------------------------
server = AgentServer()


# -----------------------------------------------------------
# RTC Session for LiveKit
# -----------------------------------------------------------
@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    """
    This function runs whenever someone connects to your agent.
    """

    # Create a voice agent session
    session = AgentSession(
        stt="deepgram/nova-3",  # Speech → Text
        llm="openai/gpt-4.1-mini",                 # Language model
        tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",  # Text → Speech
        vad=silero.VAD.load(),                    # Voice activity detection
        turn_detection=MultilingualModel(),       # User turn detection

        # Let LiveKit generate transcripts while speaking
        allow_interruptions=True,
        # tiny one-word things become 'false' interruptions that can resume
        min_interruption_words=3,
        resume_false_interruption=True,
        false_interruption_timeout=1.5,
    )

    install_interruption_handler(session)

    # Start the agent inside the LiveKit room
    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # Noise cancellation: BVC for normal users, BVCTelephony for SIP users
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC()
            ),
        ),
    )

    # Initial greeting
    await session.generate_reply(
        instructions="Greet the user and offer help."
    )


# -----------------------------------------------------------
# Run the agent
# -----------------------------------------------------------
if __name__ == "__main__":
    agents.cli.run_app(server)



