import asyncio
import logging
import re
from typing import Set

from dotenv import load_dotenv

from livekit.agents import Agent, AgentServer, JobContext, cli
from livekit.agents.voice import AgentActivity as BaseAgentActivity
from livekit.agents.voice import AgentSession as BaseAgentSession
from livekit.agents.voice import _EndOfTurnInfo
from livekit.plugins import cartesia, deepgram, openai, silero

logger = logging.getLogger("intelligent-interruption-agent")

load_dotenv()


class IntelligentInterruptionHandler:
    """
    Handles intelligent interruption logic based on agent state and user input.
    
    This class distinguishes between passive acknowledgments (like "yeah", "ok", "hmm")
    and active interruptions (like "wait", "stop", "no") based on whether the agent
    is currently speaking or silent.
    """
    
    def __init__(self):
        self.ignore_list: Set[str] = {
            'yeah', 'ok', 'hmm', 'right', 'uh-huh', 'yep', 'yup', 'aha', 'mmm', 'got it',
            'i see', 'i know', 'sure', 'okay', 'yes', 'yuppers', 'uhuh', 'mhm'
        }
        self.interrupt_list: Set[str] = {
            'wait', 'stop', 'no', 'cancel', 'hold on', 'please stop', 'never mind',
            'shut up', 'quiet', 'silence'
        }
        
    def should_ignore_input(self, text: str, agent_speaking: bool) -> bool:
        """
        Determines if user input should be ignored based on agent state and input content.
        
        Args:
            text: The user's transcribed input
            agent_speaking: Whether the agent is currently speaking
            
        Returns:
            True if the input should be ignored, False otherwise
        """
        normalized_text = self._normalize_text(text)
        
        if not agent_speaking:
            return False
            
        words = normalized_text.split()
        
        if len(words) == 1 and words[0] in self.ignore_list:
            return True
            
        for word in words:
            if word in self.interrupt_list:
                return False
                
        all_passive = all(word in self.ignore_list for word in words)
        return all_passive and agent_speaking
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison by lowercasing and removing punctuation."""
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = ' '.join(normalized.split())
        return normalized


class IntelligentAgentActivity(BaseAgentActivity):
    """
    Custom AgentActivity that implements intelligent interruption handling.
    
    Overrides the on_end_of_turn method to apply context-aware interruption logic.
    """
    
    def __init__(self, agent: Agent, sess: BaseAgentSession) -> None:
        super().__init__(agent, sess)
        self.interruption_handler = IntelligentInterruptionHandler()
        
    def on_end_of_turn(self, info: _EndOfTurnInfo) -> bool:
        """
        Override the base end_of_turn logic with intelligent interruption handling.
        
        This method is called when the audio recognition system determines the user
        has finished speaking. We apply our intelligent logic here.
        """
        agent_speaking = self._session.agent_state == "speaking"
        
        should_ignore = self.interruption_handler.should_ignore_input(info.new_transcript, agent_speaking)
        
        logger.info(
            f"End of turn - Text: '{info.new_transcript}', Agent speaking: {agent_speaking}, "
            f"Should ignore: {should_ignore}"
        )
        
        if should_ignore and agent_speaking:
            logger.info(f"Ignoring passive acknowledgment: '{info.new_transcript}' while agent is speaking")
            return True
            
        return super().on_end_of_turn(info)


class IntelligentAgentSession(BaseAgentSession):
    """
    Custom AgentSession that uses our IntelligentAgentActivity.
    """
    
    async def _update_activity(
        self,
        agent: Agent,
        *,
        previous_activity: str = "close",
        new_activity: str = "start",
        blocked_tasks: list[asyncio.Task] | None = None,
        wait_on_enter: bool = True,
    ) -> None:
        async with self._activity_lock:
            self._agent = agent

            if new_activity == "start":
                previous_agent = self._activity.agent if self._activity else None
                if agent._activity is not None and (
                    agent is not previous_agent or previous_activity != "close"
                ):
                    raise RuntimeError("cannot start agent: an activity is already running")

                self._next_activity = IntelligentAgentActivity(agent, self)
            elif new_activity == "resume":
                if agent._activity is None:
                    raise RuntimeError("cannot resume agent: no existing active activity to resume")

                self._next_activity = agent._activity

            if self._root_span_context is not None:
              
                import opentelemetry.context as otel_context
                otel_context.attach(self._root_span_context)

            previous_activity_v = self._activity
            if self._activity is not None:
                if previous_activity == "close":
                    await self._activity.drain()
                    await self._activity.aclose()
                elif previous_activity == "pause":
                    await self._activity.pause(blocked_tasks=blocked_tasks or [])

            self._activity = self._next_activity
            self._next_activity = None

            if new_activity == "start":
                await self._activity.start()
                if wait_on_enter:
                    await self._wait_on_enter(previous_activity_v)
            elif new_activity == "resume":
                await self._activity.resume()


class IntelligentAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You are a helpful assistant who responds to user queries."
            "Keep your responses concise and to the point."
            "Do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "You will speak English to the user.",
        )


server = AgentServer()


def prewarm(proc):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = IntelligentAgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        turn_detection="vad",
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        allow_interruptions=True, 
        min_interruption_words=1,  
    )

    agent = IntelligentAgent()

    await session.start(
        agent=agent,
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)