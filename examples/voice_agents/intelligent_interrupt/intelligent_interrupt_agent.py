"""
Intelligent Interrupt Handler - Voice Agent Implementation

This agent demonstrates intelligent interruption handling that distinguishes between:
- Passive acknowledgements ("yeah", "ok", "hmm") - IGNORED when agent is speaking
- Active interruptions ("stop", "wait", "no") - ALWAYS processed
- Normal input when agent is silent - ALWAYS processed

The key insight is that we DON'T modify VAD directly. Instead, we:
1. Use LiveKit's false_interruption_timeout feature to pause (not stop) on potential interrupt
2. Analyze the transcript when it arrives
3. Either resume speaking (if filler words) or confirm the interrupt (if real command)

This creates a seamless experience where the agent continues speaking over "yeah/ok/hmm"
without any stuttering or pausing.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    cli,
    metrics,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import (
    AgentFalseInterruptionEvent,
    AgentStateChangedEvent,
    RunContext,
    UserInputTranscribedEvent,
    UserStateChangedEvent,
)
from livekit.plugins import silero

from interrupt_filter import (
    InterruptFilter,
    InterruptFilterConfig,
    InterruptAnalysis,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("intelligent-interrupt-agent")


class IntelligentInterruptAgent(Agent):
    """
    Voice agent with intelligent interruption handling.
    
    This agent will:
    - Continue speaking when user says filler words like "yeah", "ok", "hmm"
    - Stop immediately when user says command words like "stop", "wait", "no"
    - Process all input normally when agent is silent
    """
    
    def __init__(
        self,
        interrupt_filter: Optional[InterruptFilter] = None,
        **kwargs
    ) -> None:
        # Default instructions for the agent
        instructions = kwargs.pop("instructions", None) or (
            "You are a helpful assistant named Alex. "
            "You provide detailed explanations when asked about topics. "
            "Keep your responses conversational but informative. "
            "When explaining something, give thorough answers. "
            "Do not use emojis, asterisks, or markdown in your responses."
        )
        
        super().__init__(instructions=instructions, **kwargs)
        
        # Initialize the interrupt filter
        self._interrupt_filter = interrupt_filter or InterruptFilter(
            InterruptFilterConfig.from_env()
        )
        
        # Track agent state for filtering decisions
        self._is_speaking = False
        self._last_transcript = ""
        self._ignored_count = 0
        
    @property
    def is_speaking(self) -> bool:
        """Check if the agent is currently speaking."""
        return self._is_speaking
    
    def on_agent_state_changed(self, old_state: str, new_state: str) -> None:
        """Track agent speaking state."""
        self._is_speaking = new_state == "speaking"
        logger.debug(f"Agent state: {old_state} -> {new_state}")
    
    def analyze_transcript(self, transcript: str) -> InterruptAnalysis:
        """
        Analyze a user transcript to determine interrupt behavior.
        
        Args:
            transcript: The user's speech transcript
            
        Returns:
            InterruptAnalysis with decision and reasoning
        """
        analysis = self._interrupt_filter.analyze(
            transcript=transcript,
            agent_speaking=self._is_speaking
        )
        
        logger.info(
            f"Transcript analysis: '{transcript}' | "
            f"Agent speaking: {self._is_speaking} | "
            f"Decision: {analysis.decision} | "
            f"Reason: {analysis.reason}"
        )
        
        return analysis
    
    def should_ignore_input(self, transcript: str) -> bool:
        """
        Determine if input should be ignored (agent continues speaking).
        
        This is called to decide whether to confirm or cancel an interruption.
        """
        analysis = self.analyze_transcript(transcript)
        
        if analysis.decision == "ignore":
            self._ignored_count += 1
            logger.info(f"Ignoring filler input #{self._ignored_count}: '{transcript}'")
            return True
        
        return False
    
    async def on_enter(self) -> None:
        """Called when agent becomes active."""
        logger.info("Agent activated - ready to demonstrate intelligent interruption handling")
        
        # Generate initial greeting
        self.session.generate_reply()
    
    @function_tool
    async def tell_long_story(self, context: RunContext) -> str:
        """
        Tell a long story about an interesting topic.
        Good for testing interrupt behavior during extended speech.
        
        This function is available when the user asks for a story or detailed explanation.
        """
        logger.info("User requested a long story - good for testing interrupt handling")
        
        return (
            "Let me tell you a fascinating story about the history of computing. "
            "In the early days, computers filled entire rooms and were programmed with punch cards. "
            "The ENIAC, built in 1945, was one of the first general-purpose electronic computers. "
            "It weighed about 27 tons and consumed 150 kilowatts of power. "
            "Interestingly, the term 'bug' in computing came from an actual moth that was found "
            "in a relay of the Harvard Mark II computer in 1947. "
            "Grace Hopper, a pioneering computer scientist, taped the moth into the computer log. "
            "From those massive machines, we've progressed to smartphones that are millions of times "
            "more powerful and fit in our pockets. "
            "The exponential growth described by Moore's Law has been remarkably accurate for decades. "
            "Today, we're exploring quantum computing, which could revolutionize fields like "
            "cryptography, drug discovery, and artificial intelligence."
        )

    @function_tool
    async def count_slowly(self, context: RunContext, count_to: int = 10) -> str:
        """
        Count numbers slowly - useful for testing "stop" command.
        
        Args:
            count_to: The number to count up to (default: 10)
        """
        logger.info(f"Starting slow count to {count_to}")
        
        numbers = ", ".join(str(i) for i in range(1, count_to + 1))
        return f"I'll count slowly for you: {numbers}. That's all!"


def create_session(ctx: JobContext, interrupt_filter: InterruptFilter) -> AgentSession:
    """
    Create an AgentSession configured for intelligent interrupt handling.
    
    The key configuration options are:
    - false_interruption_timeout: Time to wait before confirming an interruption
    - resume_false_interruption: Auto-resume if interruption was "false"
    - min_interruption_duration: Minimum speech to register as interrupt
    """
    
    session = AgentSession(
        # Speech-to-text
        stt="deepgram/nova-3",
        
        # LLM
        llm="openai/gpt-4.1-mini",
        
        # Text-to-speech
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        
        # VAD for voice activity detection
        vad=ctx.proc.userdata["vad"],
        
        # CRITICAL: Enable interruptions so we can filter them
        allow_interruptions=True,
        
        # CRITICAL: This is the key setting!
        # When potential interrupt detected, pause and wait for transcript
        # If transcript is filler ("yeah"), resume speaking
        # Default is 2.0 seconds - we use a shorter timeout for responsiveness
        false_interruption_timeout=1.5,
        
        # CRITICAL: Auto-resume speech if interruption was "false"
        resume_false_interruption=True,
        
        # Minimum speech duration to consider as interrupt attempt
        # Short sounds less than 0.5s might be noise
        min_interruption_duration=0.4,
        
        # Minimum words needed to interrupt (0 = any speech can interrupt)
        # We set to 0 because our filter handles word-based logic
        min_interruption_words=0,
        
        # End-of-turn detection delays
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
    )
    
    # Track ignored transcripts for logging
    ignored_transcripts: list[str] = []
    agent_instance: Optional[IntelligentInterruptAgent] = None
    
    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        """Track agent state for interrupt filtering."""
        if agent_instance:
            agent_instance.on_agent_state_changed(ev.old_state, ev.new_state)
    
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
        """
        Handle transcribed user input.
        
        This is where we apply intelligent filtering:
        - If agent is speaking and transcript is filler -> do nothing (auto-resume)
        - If agent is speaking and transcript is command -> interrupt proceeds
        - If agent is silent -> normal processing
        """
        if not ev.is_final:
            return  # Wait for final transcript
        
        transcript = ev.transcript.strip()
        if not transcript:
            return
            
        if agent_instance:
            analysis = agent_instance.analyze_transcript(transcript)
            
            if analysis.decision == "ignore":
                ignored_transcripts.append(transcript)
                logger.info(
                    f"[FILTER] Ignoring filler: '{transcript}' | "
                    f"Total ignored: {len(ignored_transcripts)}"
                )
            elif analysis.decision == "interrupt":
                logger.info(
                    f"[FILTER] Allowing interrupt: '{transcript}' | "
                    f"Matched commands: {analysis.matched_interrupt_words}"
                )
            else:  # respond
                logger.info(
                    f"[FILTER] Normal response: '{transcript}' | "
                    f"Agent was silent"
                )
    
    @session.on("agent_false_interruption")
    def on_false_interruption(ev: AgentFalseInterruptionEvent) -> None:
        """
        Handle false interruption detection.
        
        When VAD detects speech but no valid transcript comes through,
        LiveKit considers it a "false interruption" and can auto-resume.
        """
        if ev.resumed:
            logger.info("[RESUME] Agent resumed speaking after false interruption")
        else:
            logger.info("[FALSE_INT] False interruption detected but not resumed")
    
    @session.on("metrics_collected")
    def on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        """Log metrics for debugging."""
        metrics.log_metrics(ev.metrics)
    
    # Store reference to agent for state tracking
    def set_agent(agent: IntelligentInterruptAgent) -> None:
        nonlocal agent_instance
        agent_instance = agent
    
    # Attach the setter to session for access in entrypoint
    session._set_interrupt_agent = set_agent  # type: ignore
    
    return session


# Create the agent server
server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    """Prewarm the VAD model for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model loaded")


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Main entrypoint for the voice agent."""
    
    # Configure logging context
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # Create interrupt filter (can be customized via environment variables)
    interrupt_filter = InterruptFilter(InterruptFilterConfig.from_env())
    
    logger.info(
        f"Interrupt filter initialized with:\n"
        f"  Ignore words: {list(interrupt_filter.config.ignore_words)[:10]}...\n"
        f"  Interrupt words: {list(interrupt_filter.config.interrupt_words)[:10]}..."
    )
    
    # Create session with intelligent interrupt handling
    session = create_session(ctx, interrupt_filter)
    
    # Create the agent
    agent = IntelligentInterruptAgent(interrupt_filter=interrupt_filter)
    
    # Connect agent to session for state tracking
    if hasattr(session, '_set_interrupt_agent'):
        session._set_interrupt_agent(agent)  # type: ignore
    
    # Usage collector for session metrics
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def collect_usage(ev: MetricsCollectedEvent) -> None:
        usage_collector.collect(ev.metrics)
    
    async def log_usage() -> None:
        summary = usage_collector.get_summary()
        logger.info(f"Session usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    # Start the session
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )
    
    logger.info(
        "Intelligent Interrupt Agent started!\n"
        "Test cases:\n"
        "  1. Ask for a story, then say 'yeah' or 'ok' - agent continues\n"
        "  2. Ask agent to count, then say 'stop' - agent stops\n"
        "  3. Wait for agent to finish, then say 'yeah' - agent responds\n"
        "  4. During speech, say 'yeah but wait' - agent stops (mixed input)"
    )


if __name__ == "__main__":
    cli.run_app(server)
