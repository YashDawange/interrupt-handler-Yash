"""
Intelligent Interruption Handler Demo Agent

This example demonstrates the LiveKit Intelligent Interruption Handling system.
The agent will:
1. Ignore passive acknowledgements ("yeah", "ok", "hmm") while speaking
2. Respond to those same words when silent
3. Interrupt for real commands ("stop", "wait", "no")
4. Handle mixed inputs correctly
"""

import logging

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    InterruptionConfig,
    JobContext,
    JobProcess,
    cli,
    function_tool,
)
from livekit.agents.llm import RunContext
from livekit.plugins import deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("intelligent-interruption-agent")
load_dotenv()


class IntelligentInterruptionAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are an AI assistant demonstrating intelligent interruption handling. "
                "Your responses should be conversational and natural. "
                "When explaining something, take your time and provide detailed information. "
                "Acknowledge user backchanneling appropriately when you're silent. "
                "Keep responses clear and avoid emojis or special characters."
            ),
        )

    async def on_enter(self):
        # Greet the user and explain the demo
        self.session.say(
            "Hello! I'm demonstrating intelligent interruption handling. "
            "While I'm speaking, saying 'yeah', 'ok', or 'hmm' won't interrupt me. "
            "But words like 'stop' or 'wait' will. Let me give you a long explanation "
            "so you can try it out."
        )

    @function_tool
    async def tell_long_story(self, context: RunContext):
        """Tell a long story to demonstrate that backchanneling doesn't interrupt.
        
        This function is called when the user asks for a story or long explanation.
        """
        logger.info("Telling a long story")
        return (
            "Once upon a time, in a land far away, there was a brilliant AI system. "
            "This system had a unique ability to understand when people were really "
            "trying to interrupt versus just showing they were listening. You see, "
            "in human conversation, we often say 'yeah' or 'uh-huh' to show we're "
            "paying attention, but we don't mean to stop the speaker. The AI learned "
            "to recognize these patterns and continue speaking smoothly, just like "
            "a human would. This made conversations feel much more natural and less "
            "awkward. People loved talking to this AI because it felt like chatting "
            "with a friend who understood social cues."
        )

    @function_tool
    async def count_numbers(self, context: RunContext):
        """Count from 1 to 10 slowly.
        
        This allows testing interruptions during counting.
        """
        logger.info("Counting numbers")
        return "One, two, three, four, five, six, seven, eight, nine, ten."

    @function_tool
    async def explain_concept(self, context: RunContext, concept: str):
        """Explain a concept in detail.
        
        Args:
            concept: The concept to explain
        """
        logger.info(f"Explaining concept: {concept}")
        
        explanations = {
            "ai": (
                "Artificial Intelligence, or AI, is a fascinating field of computer science. "
                "It involves creating systems that can perform tasks that typically require "
                "human intelligence. This includes things like understanding language, "
                "recognizing patterns, making decisions, and solving problems. Modern AI "
                "uses techniques like machine learning and neural networks to learn from data."
            ),
            "default": (
                f"The concept of {concept} is quite interesting. It encompasses various "
                "principles and applications that have evolved over time. Understanding "
                "it requires considering multiple perspectives and contexts."
            )
        }
        
        return explanations.get(concept.lower(), explanations["default"])


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # Configure intelligent interruption handling
    # You can customize the ignore words list here
    interruption_config = InterruptionConfig(
        ignore_words=[
            "yeah", "ok", "okay", "hmm", "uh-huh", "mhm", 
            "right", "aha", "gotcha", "sure", "yep", "yup", "mm-hmm"
        ],
        case_sensitive=False,
        enabled=True
    )
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        # Enable intelligent interruption handling
        interruption_config=interruption_config,
    )

    await session.start(
        agent=IntelligentInterruptionAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)
