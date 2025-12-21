"""
Example Agent - Demonstrates intelligent interrupt handling.

This file shows how to create a voice agent with intelligent interrupt handling
using the modular components from this package.

Run with:
    cd examples/voice_agents
    python intelligent_interrupt/agent.py dev
    
Or:
    cd examples/voice_agents/intelligent_interrupt
    python agent.py dev
"""

from __future__ import annotations

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
)
from livekit.agents.llm import function_tool
from livekit.plugins import silero

# Handle both package import and direct execution
try:
    from . import (
        InterruptFilter,
        InterruptFilterConfig,
        get_session_options,
        attach_interrupt_handlers,
    )
except ImportError:
    # Running directly: python agent.py
    from filter import InterruptFilter, InterruptFilterConfig
    from session_integration import get_session_options, attach_interrupt_handlers

load_dotenv()

logger = logging.getLogger("intelligent-interrupt-agent")
logger.setLevel(logging.INFO)


# =============================================================================
# VOICE AGENT
# =============================================================================

class IntelligentInterruptAgent(Agent):
    """Voice agent with intelligent interruption handling."""
    
    def __init__(self, **kwargs) -> None:
        instructions = kwargs.pop("instructions", None) or (
            "You are a helpful assistant. Keep responses conversational. "
            "If interrupted with 'stop' or 'wait', acknowledge and ask how to help."
        )
        super().__init__(instructions=instructions, **kwargs)
    
    async def on_enter(self) -> None:
        """Called when agent becomes active."""
        logger.info("Agent ready!")
        self.session.generate_reply()
    
    @function_tool
    async def tell_long_story(self, context: RunContext) -> str:
        """Tell a long story - good for testing interrupt behavior."""
        return (
            "Let me tell you a fascinating story about computing history. "
            "The ENIAC, built in 1945, was one of the first computers. "
            "It weighed 27 tons and consumed 150 kilowatts of power. "
            "The term 'bug' came from an actual moth found in Harvard's Mark II. "
            "Grace Hopper taped the moth into the computer log."
        )


# =============================================================================
# SERVER SETUP
# =============================================================================

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    """Prewarm models for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()
    proc.userdata["interrupt_filter"] = InterruptFilter(InterruptFilterConfig.from_env())
    logger.info("Models loaded")


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Main entrypoint for the voice agent."""
    
    interrupt_filter: InterruptFilter = ctx.proc.userdata["interrupt_filter"]
    
    # Create session with intelligent interrupt settings
    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2",
        vad=ctx.proc.userdata["vad"],
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
        **get_session_options(),  # Applies allow_interruptions=True, min_interruption_words=999
    )
    
    # Attach interrupt handlers - just one line!
    attach_interrupt_handlers(session, interrupt_filter, log_decisions=True)
    
    # Metrics collection
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage() -> None:
        summary = usage_collector.get_summary()
        logger.info(f"Session usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Create and start agent
    agent = IntelligentInterruptAgent()
    
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(audio_input=room_io.AudioInputOptions()),
    )
    
    logger.info(
        "\n=== Intelligent Interrupt Agent ===\n"
        "  'yeah', 'ok' while speaking → NO pause\n"
        "  'stop', 'wait' while speaking → Agent stops\n"
    )


if __name__ == "__main__":
    cli.run_app(server)
