"""
Intelligent Interruption Handling Demo

This example demonstrates the intelligent interruption filtering feature.
The agent will ignore backchannel words like "yeah", "ok", "hmm" when speaking,
but will respond to them when silent, and will always stop for command words
like "stop", "wait", "no".
"""

import logging

from dotenv import load_dotenv

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli, function_tool
from livekit.plugins import deepgram, openai, silero

logger = logging.getLogger("intelligent-interruption-demo")
logger.setLevel(logging.INFO)

load_dotenv()


@function_tool
async def tell_long_story(context):
    """Tell a long story to demonstrate backchannel handling."""
    return """Once upon a time, in a land far away, there lived a wise old wizard. 
    The wizard spent his days studying ancient texts and practicing powerful spells. 
    One day, a young apprentice came to learn from the wizard. The wizard taught the 
    apprentice about the importance of patience, wisdom, and understanding. Together, 
    they embarked on many adventures, facing challenges and overcoming obstacles. 
    Through their journey, they learned that true magic comes from within, and that 
    the greatest power is the power of friendship and knowledge."""


async def entrypoint(ctx: JobContext):
    """Main entrypoint for the agent."""
    await ctx.connect()
    
    logger.info(f"Connected to room: {ctx.room.name}")
    
    # Create agent with instructions
    agent = Agent(
        instructions="""You are a friendly storytelling assistant. 
        When users ask you to tell a story, use the tell_long_story function.
        Speak slowly and clearly, and don't be interrupted by simple acknowledgments 
        like 'yeah', 'ok', or 'hmm'. However, if the user says 'stop', 'wait', or 
        other command words, stop immediately and listen to them.""",
        tools=[tell_long_story],
    )
    
    # Create session with intelligent interruption filtering enabled (default)
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="echo"),
        # Intelligent interruption filtering is enabled by default
        enable_backchannel_filter=True,
        # You can disable it to see the difference:
        # enable_backchannel_filter=False,
    )
    
    # Start the session
    await session.start(agent=agent, room=ctx.room)
    
    # Generate initial greeting
    await session.generate_reply(
        instructions="Greet the user and offer to tell them a story. "
        "Mention that they can say 'stop' or 'wait' if they want to interrupt."
    )
    
    logger.info("Agent started successfully")


def main():
    """Run the agent."""
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
