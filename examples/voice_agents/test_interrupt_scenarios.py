"""
Test Script for Intelligent Interruption Handling

This script provides a simpler agent for testing specific scenarios.
It's designed to make testing easier by having the agent read specific scripts
that allow for controlled testing of the interruption handling feature.
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
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("test-interrupt-scenarios")
logger.setLevel(logging.DEBUG)

load_dotenv()


class TestAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a test assistant for the interruption handling system. "
                "When the user asks you to test a scenario, follow their instructions exactly. "
                "Keep responses natural and conversational. "
                "Do not use emojis or markdown."
            )
        )

    async def on_enter(self):
        """Greet the user and offer test scenarios."""
        self.session.generate_reply()

    @function_tool
    async def count_slowly(self, max_number: int = 20):
        """
        Count slowly from 1 to max_number.
        User can test by saying 'yeah', 'ok' during counting (should not interrupt)
        or 'stop', 'wait' (should interrupt).
        
        Args:
            max_number: The number to count up to (default 20)
        """
        logger.info(f"Starting to count to {max_number}")
        count_text = ", ".join([str(i) for i in range(1, max_number + 1)])
        return f"I'll count to {max_number} now: {count_text}. Done!"

    @function_tool
    async def read_alphabet(self):
        """
        Recite the alphabet slowly.
        Good for testing interruptions during a long sequence.
        """
        logger.info("Starting alphabet recitation")
        return "I'll recite the alphabet now: A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z. Done!"

    @function_tool
    async def explain_topic(self, topic: str):
        """
        Explain a topic in detail.
        
        Args:
            topic: The topic to explain (e.g., "history of computers", "solar system")
        """
        logger.info(f"Explaining topic: {topic}")
        return f"Let me explain {topic} in detail. This will be a comprehensive explanation that takes time to deliver."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Entry point with intelligent interruption handling."""
    ctx.log_context_fields = {"room": ctx.room.name}
    
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        allow_interruptions=True,
        min_interruption_duration=0.3,
        min_interruption_words=0,
        # Key feature: backchannel words
        backchannel_words=['yeah', 'ok', 'hmm', 'right', 'uh-huh', 'aha', 'mm-hmm', 'mhmm', 'yep', 'yup', 'sure', 'alright', 'okay'],
    )
    
    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        logger.info(f"[AGENT STATE] {ev.old_state} -> {ev.new_state}")
    
    @session.on("user_state_changed")
    def _on_user_state_changed(ev):
        logger.info(f"[USER STATE] {ev.old_state} -> {ev.new_state}")
    
    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev):
        logger.info(f"[TRANSCRIPT ({'FINAL' if ev.is_final else 'INTERIM'})] {ev.transcript}")

    await session.start(
        agent=TestAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


if __name__ == "__main__":
    cli.run_app(server)

