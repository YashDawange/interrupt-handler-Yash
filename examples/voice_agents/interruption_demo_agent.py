"""Example agent demonstrating semantic interruption handling.

This example shows how to enable intelligent interruption control that:
- Ignores backchannel speech ("yeah", "ok", "hmm") while agent is speaking
- Immediately interrupts on commands ("stop", "wait", "no")
- Responds normally to all input when agent is silent
"""

import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice.interruption import InterruptionConfig
from livekit.plugins import silero

logger = logging.getLogger("interruption-demo-agent")

load_dotenv()


class InterruptionDemoAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Alex. You are a helpful AI assistant. "
            "When asked to explain something, provide detailed, multi-sentence responses. "
            "Keep responses natural and conversational, but informative. "
            "You speak English to the user."
        )

    async def on_enter(self):
        # Greet the user when the agent enters
        self.session.generate_reply(
            instructions="instructions: Greet the user and ask how you can help them today."
        )

    @function_tool
    async def explain_topic(self, topic: str):
        """Called when the user asks for an explanation of a topic.

        Args:
            topic: The topic to explain
        """
        logger.info(f"Explaining topic: {topic}")
        return f"Here's a detailed explanation of {topic}..."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "participant": ctx.participant.identity,
    }

    logger.info("Starting semantic interruption demo agent")

    # Create custom interruption configuration
    interruption_config = InterruptionConfig(
        # Default ignore words work well for English backchannel
        # ignore_words={"yeah", "ok", "hmm", ...}  # (default)
        #
        # Default command words for explicit interruption
        # command_words={"stop", "wait", "no", ...}  # (default)
        #
        # By default, substantive content also interrupts
        interrupt_on_normal_content=True,  # Set to False to only interrupt on commands
    )

    # Initialize agent session with semantic interruption enabled
    session = AgentSession(
        # Model configuration
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-2.0:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        vad=ctx.proc.userdata["vad"],
        # CRITICAL: Must disable audio discarding to keep STT active during TTS
        # This allows the controller to receive transcripts even while agent is speaking
        discard_audio_if_uninterruptible=False,
        # Enable semantic interruption handling
        interruption_config=interruption_config,
        # Optional: Configure other interruption-related settings
        # resume_false_interruption=True,
        # false_interruption_timeout=2.0,
    )

    # Start the session with the demo agent
    await session.start(InterruptionDemoAgent(), room=ctx.room)


if __name__ == "__main__":
    """
    To run this demo:

    1. Set up your environment:
       export LIVEKIT_URL="<your-livekit-url>"
       export LIVEKIT_API_KEY="<your-api-key>"
       export LIVEKIT_API_SECRET="<your-api-secret>"
       export OPENAI_API_KEY="<your-openai-key>"
       export DEEPGRAM_API_KEY="<your-deepgram-key>"

    2. Run the agent:
       python examples/voice_agents/interruption_demo_agent.py dev

    3. Test scenarios:
       - Ask: "Tell me about quantum physics" and say "yeah", "ok", "hmm" while it speaks
         Expected: Agent continues sp Speaking without pausing
       
       - While agent is speaking, say: "Stop"
         Expected: Agent stops immediately
       
       - While agent is speaking, say: "Yeah okay but wait a second"
         Expected: Agent stops (detects "wait")
       
       - Agent asks "Are you ready?" and stops, then you say: "Yeah"
         Expected: Agent responds to "yeah" as normal input
    """
    cli.run_app(server)
