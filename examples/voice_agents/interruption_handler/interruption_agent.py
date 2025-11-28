"""
Intelligent Interruption Handler Agent

A voice agent that detects user interruptions, analyzes their context and intent,
and responds with appropriate resume strategies.
"""

import logging
import asyncio
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.agents.voice import (
    AgentStateChangedEvent,
    UserStateChangedEvent,
    SpeechCreatedEvent,
    UserInputTranscribedEvent,
)
from livekit import rtc
from livekit.plugins import deepgram, openai, cartesia, silero

from context_analyzer import ContextAnalyzer, InterruptionContext

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("interruption-agent")

server = AgentServer()


@dataclass
class InterruptionEvent:
    """Tracks interruption details with context analysis"""
    timestamp: datetime = field(default_factory=datetime.now)
    agent_was_speaking: bool = False
    agent_speech_text: str = ""
    user_utterance: str = ""
    interruption_point: float = 0.0
    context: Optional[InterruptionContext] = None
    
    def __str__(self):
        base = (
            f"Interruption at {self.timestamp.strftime('%H:%M:%S')} | "
            f"Agent: '{self.agent_speech_text[:50]}...' | "
            f"User: '{self.user_utterance}' | "
            f"Point: {self.interruption_point:.1%}"
        )
        if self.context:
            base += f"\n   Type: {self.context.interruption_type.value} | Strategy: {self.context.recommended_strategy.value}"
        return base


class InterruptionAgent(Agent):
    """Voice agent with intelligent interruption handling"""
    
    def __init__(self):
        super().__init__(
            instructions="""You are an intelligent voice assistant that excels at natural conversation flow.

INTERRUPTION HANDLING:
1. AGREEMENT/INTEREST ("That's interesting"):
   - Acknowledge briefly then CONTINUE with detailed explanation
   - Example: "Exactly! So continuing with AI, there are several key components..."

2. URGENT QUESTIONS:
   - Answer briefly, then return to original topic
   
3. CORRECTIONS:
   - Acknowledge and provide correct information

4. STOP REQUESTS:
   - Stop immediately and ask what they'd like to know

5. TOPIC CHANGES:
   - Smoothly transition to new topic

6. CLARIFICATION:
   - Restart with simpler explanation

CRITICAL: When users show interest, CONTINUE explaining comprehensively (30-60 seconds).
DO NOT stop early or ask if they have questions. Provide detailed, flowing explanations."""
        )
        
        self.agent_state: str = "initializing"
        self.user_state: str = "listening"
        self.current_speech_text = ""
        self.speech_start_time: Optional[datetime] = None
        self.interruption_events: list[InterruptionEvent] = []
        self.active_speech_handle = None
        self.context_analyzer: Optional[ContextAnalyzer] = None
        self.conversation_history: list[str] = []
        self.last_user_transcript: str = ""
        self.resume_context: Optional[dict] = None
        self.interrupted_speech_content: str = ""
        
        logger.info("✅ InterruptionAgent initialized")
    
    async def on_enter(self):
        """Initialize agent and set up event handlers"""
        logger.info("🎤 Interruption handler active")
        
        session_llm = self.session._llm if hasattr(self.session, '_llm') else None
        self.context_analyzer = ContextAnalyzer(llm=session_llm)
        
        @self.session.on("agent_state_changed")
        def on_agent_state_changed(ev: AgentStateChangedEvent):
            logger.info(f"🤖 Agent state: {ev.old_state} → {ev.new_state}")
            self.agent_state = ev.new_state
            
            if ev.new_state == "speaking":
                self.speech_start_time = datetime.now()
            elif ev.old_state == "speaking":
                duration = self._get_speech_duration()
                logger.info(f"🛑 Agent stopped speaking ({duration:.2f}s)")
        
        @self.session.on("user_state_changed")
        def on_user_state_changed(ev: UserStateChangedEvent):
            logger.info(f"👤 User state: {ev.old_state} → {ev.new_state}")
            old_user_state = self.user_state
            self.user_state = ev.new_state
            
            if ev.new_state == "speaking" and self.agent_state == "speaking":
                self._log_quick_interruption()
        
        @self.session.on("user_input_transcribed")
        def on_user_input_transcribed(ev: UserInputTranscribedEvent):
            if ev.is_final:
                self.last_user_transcript = ev.transcript
                self.conversation_history.append(f"User: {ev.transcript}")
                logger.debug(f"📝 User said: {ev.transcript}")
        
        @self.session.on("speech_created")
        def on_speech_created(ev: SpeechCreatedEvent):
            logger.info(f"💬 Speech created: source={ev.source}")
            self.active_speech_handle = ev.speech_handle
            self.interrupted_speech_content = ""
            self.current_speech_text = "Agent speech in progress..."
            
            async def check_interruption():
                await ev.speech_handle.wait_for_playout()
                if ev.speech_handle.interrupted:
                    logger.warning(f"⚠️  Speech interrupted!")
                    self.interrupted_speech_content = self.current_speech_text
                    
                    # Wait for transcript to arrive (STT processing delay)
                    await asyncio.sleep(2.5)
                    await self._analyze_and_handle_interruption()
                else:
                    logger.info("✅ Speech completed")
            
            asyncio.create_task(check_interruption())
        
        logger.info("✅ Event handlers registered")
    
    def _log_quick_interruption(self):
        """Log interruption immediately for visibility"""
        interruption = InterruptionEvent(
            timestamp=datetime.now(),
            agent_was_speaking=True,
            agent_speech_text=self.current_speech_text,
            user_utterance="<interrupting>",
            interruption_point=self._calculate_interruption_point()
        )
        
        self.interruption_events.append(interruption)
        
        logger.warning("=" * 70)
        logger.warning("🔴 INTERRUPTION DETECTED!")
        logger.warning(f"   {interruption}")
        logger.warning(f"   Total interruptions: {len(self.interruption_events)}")
        logger.warning("=" * 70)
    
    async def _analyze_and_handle_interruption(self):
        """Analyze interruption context and execute appropriate strategy"""
        if not self.context_analyzer or not self.interruption_events:
            return
        
        recent_interruption = self.interruption_events[-1]
        recent_interruption.user_utterance = self.last_user_transcript or "<no transcript>"
        
        logger.info("🔍 Analyzing interruption context...")
        
        try:
            context = await self.context_analyzer.analyze_interruption(
                user_utterance=recent_interruption.user_utterance,
                agent_speech=recent_interruption.agent_speech_text,
                conversation_history=self.conversation_history[-10:],
                interruption_point=recent_interruption.interruption_point
            )
            
            recent_interruption.context = context
            
            logger.warning("=" * 70)
            logger.warning("🧠 CONTEXT ANALYSIS COMPLETE")
            logger.warning(f"   Type: {context.interruption_type.value} ({context.confidence:.0%} confident)")
            logger.warning(f"   Intent: {context.user_intent}")
            logger.warning(f"   Strategy: {context.recommended_strategy.value}")
            logger.warning("=" * 70)
            
            await self._execute_resume_strategy(context)
            
        except Exception as e:
            logger.error(f"Error analyzing interruption: {e}", exc_info=True)
    
    async def _execute_resume_strategy(self, context: InterruptionContext):
        """Execute the appropriate resume strategy"""
        from context_analyzer import ResumeStrategy
        
        strategy = context.recommended_strategy
        logger.info(f"🎯 Executing strategy: {strategy.value}")
        
        if strategy == ResumeStrategy.ACKNOWLEDGE_AND_CONTINUE:
            await self._acknowledge_and_continue(context)
        elif strategy == ResumeStrategy.ACKNOWLEDGE_AND_CHANGE:
            await self._acknowledge_and_change_topic(context)
        elif strategy == ResumeStrategy.ANSWER_AND_RESUME:
            await self._answer_and_resume(context)
        elif strategy == ResumeStrategy.RESTART_RESPONSE:
            await self._restart_explanation(context)
        elif strategy == ResumeStrategy.STOP_AND_LISTEN:
            await self._stop_and_listen(context)
        elif strategy == ResumeStrategy.APOLOGIZE_AND_CORRECT:
            await self._apologize_and_correct(context)
    
    async def _acknowledge_and_continue(self, context: InterruptionContext):
        """Brief acknowledgment, then detailed continuation"""
        logger.info("📍 Strategy: Acknowledge + Continue")
        
        self.resume_context = {
            'original_topic': context.agent_topic,
            'original_speech': context.agent_was_saying,
            'interruption_point': context.interruption_point,
            'interrupted_content': self.interrupted_speech_content
        }
        
        topic = context.agent_topic.lower().replace('explanation', '').replace('discussion', '').strip()
        natural_continuation = f"Exactly! So to dive deeper into {topic}, there are several key aspects I should cover..."
        
        await self.session.say(natural_continuation, allow_interruptions=True)
    
    async def _acknowledge_and_change_topic(self, context: InterruptionContext):
        """Switch to user's new topic"""
        logger.info("📍 Strategy: Acknowledge + Change Topic")
        response = f"That's interesting! Let's talk about {context.user_intent.lower()} instead."
        await self.session.say(response, allow_interruptions=True)
    
    async def _answer_and_resume(self, context: InterruptionContext):
        """Answer question then resume original topic"""
        logger.info("📍 Strategy: Answer + Resume")
        
        self.resume_context = {
            'original_topic': context.agent_topic,
            'original_speech': context.agent_was_saying
        }
        
        response = f"Good question! Let me quickly address that: {context.user_intent}. Now, back to what I was explaining about {context.agent_topic}."
        await self.session.say(response, allow_interruptions=True)
    
    async def _restart_explanation(self, context: InterruptionContext):
        """Start over with clearer explanation"""
        logger.info("📍 Strategy: Restart Explanation")
        response = f"Let me explain {context.agent_topic} in a simpler way. Let me start over."
        await self.session.say(response, allow_interruptions=True)
    
    async def _stop_and_listen(self, context: InterruptionContext):
        """Stop and wait for user"""
        logger.info("📍 Strategy: Stop and Listen")
        response = "Sure, what would you like to know?"
        await self.session.say(response, allow_interruptions=True)
    
    async def _apologize_and_correct(self, context: InterruptionContext):
        """Accept correction gracefully"""
        logger.info("📍 Strategy: Apologize and Correct")
        response = f"You're absolutely right, thank you for the correction. {context.user_intent}."
        await self.session.say(response, allow_interruptions=True)
    
    def _get_speech_duration(self) -> float:
        """Calculate how long agent has been speaking"""
        if self.speech_start_time:
            return (datetime.now() - self.speech_start_time).total_seconds()
        return 0.0
    
    def _calculate_interruption_point(self) -> float:
        """Estimate how far into speech the interruption occurred (0.0-1.0)"""
        return 0.5


@server.entrypoint(path="/interruption-handler")
async def handler(ctx: JobContext):
    """Agent entry point"""
    logger.info("🚀 Starting agent session...")
    
    await ctx.connect()
    logger.info("✅ Connected to room")
    
    # Prewarm VAD for faster startup
    await silero.VAD.load()
    
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )
    
    agent = InterruptionAgent()
    await session.start(agent=agent, room=ctx.room)
    
    logger.info("🎯 Agent session started successfully")


@server.worker_entrypoint
async def start_worker(ctx: JobProcess):
    """Worker initialization"""
    await ctx.run()


if __name__ == "__main__":
    cli.run_app(server)
