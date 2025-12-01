import asyncio
import logging
import os
import time
import inspect 
from dataclasses import dataclass
from typing import Literal, Optional, Set

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    cli,
)
from livekit.agents.voice import (
    AgentStateChangedEvent,
    UserInputTranscribedEvent,
)
from livekit.plugins import assemblyai, cartesia, groq, silero


# INIT
load_dotenv()
logger = logging.getLogger("intelligent-interruption")
logger.setLevel(logging.INFO)


# CONFIG

@dataclass
class InterruptionConfig:
    backchannel_words: Set[str]
    interruption_words: Set[str]


@dataclass
class PendingInterruption:
    timestamp: float
    transcript: Optional[str]
    classification: Optional[str]


# CLASSIFIER
class InputClassifier:
    InputType = Literal["backchannel", "interruption", "normal"]

    def __init__(self, config: InterruptionConfig):
        self.config = config

    def classify(self, text: str) -> InputType:
        if not text or not text.strip():
            return "normal"

        tokens = text.lower().strip().split()
        words = {t.strip('.,!?;:\'"') for t in tokens if t.strip()}

        if words & self.config.interruption_words:
            return "interruption"

        if words and words.issubset(self.config.backchannel_words):
            return "backchannel"

        return "normal"


# ADVANCED INTERRUPTION HANDLER
class AdvancedInterruptionHandler:
    def __init__(self, session: AgentSession, config: InterruptionConfig):
        self.session = session
        self.config = config
        self.classifier = InputClassifier(config)

        self.is_agent_speaking = False
        self._current_speech_id = 0

        # Dropper flag (suppresses next user input)
        self._drop_next_user_msg = False

        # Patch internal message handler for suppression
        self._patch_dropper() # Patches the internal LiveKit method

        # Setup listeners
        self._setup_listeners()

    def _patch_dropper(self):
        """
        Overrides LiveKit's internal transcript handler by wrapping the async function
        with a synchronous caller, resolving the "was never awaited" error and
        fixing the NoneType error when forwarding messages.
        """
        
        # TARGETED METHOD: Found to be responsible for processing final transcript
        NEW_METHOD_NAME = "_user_input_transcribed"

        if not hasattr(self.session, NEW_METHOD_NAME):
            logger.warning(f"⚠ Could not patch dropper hook — Internal API '{NEW_METHOD_NAME}' not found.")
            return

        # 1. Get the original method
        original_hook = getattr(self.session, NEW_METHOD_NAME)

        # 2. Define the ASYNC logic that performs the drop/forward
        async def async_dropper_logic(ev): 
            # Logic for HARD STOP suppression
            if self._drop_next_user_msg:
                logger.info(" Dropping user message (HARD STOP mode)")
                self._drop_next_user_msg = False
                return
            
            # Logic for forwarding the message when NOT dropping
            #  FIX for TypeError: Check if original_hook returns an awaitable before awaiting it.
            result = original_hook(ev)
            if inspect.isawaitable(result):
                await result
            # If it returns None, we simply do nothing, fixing the TypeError.

        # 3. Define the SYNCHRONOUS function that replaces the original hook
        def sync_wrapper(ev):
            """Schedules the async dropper logic to run without blocking the calling thread."""
            try:
                # We schedule the coroutine as a task to be run on the existing event loop
                asyncio.create_task(async_dropper_logic(ev))
            except RuntimeError:
                logger.error("Failed to create task for dropper logic - RuntimeError")

        # 4. Apply the patch using the SYNCHRONOUS wrapper
        setattr(self.session, NEW_METHOD_NAME, sync_wrapper)
        logger.info(f" Successfully patched dropper hook on: {NEW_METHOD_NAME} using sync wrapper")

    def _setup_listeners(self):
        @self.session.on("agent_state_changed")
        def _on_agent_state_changed(ev: AgentStateChangedEvent):
            was_speaking = self.is_agent_speaking
            self.is_agent_speaking = ev.new_state == "speaking"

            logger.info(f"Agent state: {ev.old_state} → {ev.new_state}")

            if not was_speaking and self.is_agent_speaking:
                self._current_speech_id += 1

        @self.session.on("user_input_transcribed")
        def _on_transcribed(ev: UserInputTranscribedEvent):
            if ev.is_final:
                asyncio.create_task(self._process(ev.transcript))

    async def _process(self, transcript: str):
        logger.info(
            f"Processing: '{transcript}' (speaking={self.is_agent_speaking}, "
            f"speech_id={self._current_speech_id})"
        )

        classification = self.classifier.classify(transcript)
        logger.info(f"Classification → {classification}")

        pending = PendingInterruption(
            timestamp=time.time(),
            transcript=transcript,
            classification=classification,
        )

        # CASE 1 — Agent speaking
        if self.is_agent_speaking:

            # Ignore backchannels while speaking
            if classification == "backchannel":
                logger.info(" Backchannel while speaking → ignored (attempting seamless resume)")
                
                # We tell the agent to resume immediately to achieve seamless continuation
                try:
                    await self.session.resume_interrupted_speech()
                except:
                    pass
                return

            # All other input (stop / wait / anything / normal statement) → HARD STOP
            logger.info(" Interrupt while speaking → HARD STOP")
            await self._hard_stop(pending)
            return

        # CASE 2 — Agent silent → NORMAL BEHAVIOR
        # Respond normally to anything including backchannels
        logger.info(" Agent silent → normal processing")
        # (We do nothing → Patched hook allows message to proceed to LLM)
        return

    #
    async def _hard_stop(self, pending: PendingInterruption):
        """
        Fully suppress all replies AND prevent LLM from responding using the dropper hook.
        """
        logger.info(
            f" HARD STOP triggered: speech_id={self._current_speech_id}, "
            f"text='{pending.transcript}'"
        )

        #  Stop TTS immediately
        try:
            await self.session.interrupt(force=True)
        except:
            pass

        # Drop next user message 
        self._drop_next_user_msg = True

        # don't reuse transcript
        pending.transcript = None

        return



# CONFIG LOADER

def create_config() -> InterruptionConfig:
    back = "yeah,yes,yep,ok,okay,hmm,mhmm,uh-huh,right,sure,aha,alright,yup"
    intr = "stop,wait,no,pause,hold,hold on"

    return InterruptionConfig(
        backchannel_words={w.strip() for w in back.split(",")},
        interruption_words={w.strip() for w in intr.split(",")},
    )



# ASSISTANT AGENT

class AssistantAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are a helpful AI assistant. "
                "You give long, detailed responses. "
                "Ignore yeah/ok/hmm while speaking. "
                "When silent, respond normally to any input and continue the past convesation."
            )
        )

    async def on_enter(self):
        self.session.generate_reply(
            instructions="Give a long greeting (15+ seconds)."
        )



# ENTRYPOINT

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):

    config = create_config()

    logger.info("=" * 80)
    logger.info(" ADVANCED INTERRUPTION HANDLER STARTING")
    logger.info("=" * 80)
    logger.info(f"Backchannels: {config.backchannel_words}")
    logger.info(f"Interruptions: {config.interruption_words}")
    logger.info("=" * 80)

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=assemblyai.STT(),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=cartesia.TTS(),

        allow_interruptions=True,
        min_interruption_words=999,
        false_interruption_timeout=None,
        resume_false_interruption=False, 
    )

    handler = AdvancedInterruptionHandler(session, config)

    await session.start(agent=AssistantAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)