"""
Intelligent Interruption Handling Example

This example demonstrates the intelligent interruption filter that distinguishes between:
- Passive acknowledgements (backchanneling): "yeah", "ok", "hmm" while agent is speaking → ignored
- Active interruptions: "wait", "stop", "no" → always triggers interrupt
- Normal conversation when agent is silent → processed normally

The agent will tell a long story and demonstrate how it handles different types of user input.
"""

import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero, openai, deepgram

logger = logging.getLogger("interruption-handler-agent")
logger.setLevel(logging.INFO)

load_dotenv()


class InterruptionHandlerAgent(Agent):
    """
    Demo agent that showcases intelligent interruption handling.

    The agent tells a long story about history and demonstrates how it reacts to:
    1. Soft acknowledgements (yeah, ok, hmm) - ignored while speaking
    2. Interrupt commands (stop, wait) - causes agent to stop and listen
    3. Normal input when silent - processed as usual
    """

    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a knowledgeable history teacher. Your name is Professor Alex.

When the user greets you or asks you to start, tell a comprehensive and detailed story about 
the history of the internet. Make it engaging, and aim to speak for at least 60-90 seconds.

Important: Speak naturally and don't interrupt yourself based on the user saying "yeah", "ok", 
"hmm", or similar acknowledgement sounds. These are signs they're listening, not interrupting.
Continue your story seamlessly.

However, if the user says "stop", "wait", "hold on", "actually", "but wait", or similar 
command words, immediately stop talking and listen to what they have to say.

Keep your responses concise when answering questions, but stories can be longer.
Do not use markdown, asterisks, or special characters in your responses."""
        )

    async def on_enter(self):
        """Generate initial greeting when agent enters."""
        self.session.generate_reply(
            text="Hello! I'm Professor Alex. Would you like me to tell you about the fascinating history of the internet? Just say 'yes' or 'go' and I'll share a detailed story with you."
        )

    @function_tool
    async def acknowledge_feedback(self, context: RunContext, feedback: str):
        """
        Process user feedback or questions that interrupt the agent.

        Args:
            feedback: The user's feedback or question

        Returns:
            Acknowledgement of the feedback
        """
        logger.info(f"Processing user feedback: {feedback}")
        return f"Thank you for your input: {feedback}. I understand. Would you like me to continue the story or start over?"


server = AgentServer()


def prewarm(proc: JobProcess):
    """Preload models for faster startup."""
    logger.info("Prewarming models...")
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main agent session entry point."""
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    logger.info(f"Starting agent session in room: {ctx.room.name}")

    session = AgentSession(
        # Speech-to-text for understanding the user
        stt="deepgram/nova-3",
        # LLM for generating responses
        llm="openai/gpt-oss-120b",           
        # Text-to-speech for the agent's voice
        # tts="openai/tts-1-hd",
        tts = "playai-tts",
        # Voice activity detection for interruption handling
        vad=ctx.proc.userdata["vad"],
        # Allow interruptions for a more natural conversation
        allow_interruptions=True,
        # Enable preemptive generation to reduce latency
        preemptive_generation=True,
        # Settings for false positive interruption handling
        # If user makes noise but doesn't speak for 2 seconds, resume
        false_interruption_timeout=2.0,
        resume_false_interruption=True,
    )

    agent = InterruptionHandlerAgent()
    await session.run(agent=agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
