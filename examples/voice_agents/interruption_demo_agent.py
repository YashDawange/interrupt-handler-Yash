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
from livekit.plugins import deepgram, openai, silero

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
    # Set up logging context
    logger.info("Starting semantic interruption demo agent")

    # Option 1: Create custom interruption configuration
    interruption_config = InterruptionConfig(
        # Words to ignore while the agent is speaking
        ignore_words={
            "yeah", "ok", "okay", "hmm", "mm", "uh", "uh-huh", "mm-hmm",
            "right", "sure", "yep", "yup", "mhm", "ah", "oh", "yes"
        },
        # Words that immediately interrupt the agent
        command_words={"stop", "wait", "no", "pause", "cancel"},
        interrupt_on_normal_content=True,
    )
    
    # Option 2: Load configuration from environment variables
    # Uncomment to use environment-based config:
    # interruption_config = InterruptionConfig.from_env()
    #
    # Set these environment variables to customize:
    # export INTERRUPTION_IGNORE_WORDS="yeah,ok,hmm,gotcha"
    # export INTERRUPTION_COMMAND_WORDS="stop,wait,pause,cancel"
    # export INTERRUPTION_COMMAND_PHRASES="hold on,wait a sec"
    # export INTERRUPTION_INTERRUPT_ON_NORMAL="true"

    # Initialize agent session with semantic interruption enabled
    session = AgentSession(
        # Model configuration
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts=deepgram.TTS(),  # Using Deepgram TTS for lower latency
        vad=ctx.proc.userdata["vad"],
        # CRITICAL: Must disable audio discarding to keep STT active during TTS
        # This allows the controller to receive transcripts even while agent is speaking
        discard_audio_if_uninterruptible=False,
        # Enable semantic interruption handling
        interruption_config=interruption_config,
        # Optional: Configure other interruption-related settings
        resume_false_interruption=True,
        false_interruption_timeout=2.0,
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
