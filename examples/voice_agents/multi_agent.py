import logging
import re
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from livekit import api
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ChatContext,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    metrics,
)
from livekit.agents.job import get_job_context
from livekit.agents.llm import function_tool
from livekit.agents.voice import MetricsCollectedEvent, UserInputTranscribedEvent
from livekit.plugins import deepgram
from livekit.plugins import openai
from livekit.plugins import silero

# uncomment to enable Krisp BVC noise cancellation, currently supported on Linux and MacOS
# from livekit.plugins import noise_cancellation

## The storyteller agent is a multi-agent that can handoff the session to another agent.
## This example demonstrates more complex workflows with multiple agents.
## Each agent could have its own instructions, as well as different STT, LLM, TTS,
## or realtime models.

logger = logging.getLogger("multi-agent")

load_dotenv()

# Ensure we see informative logs while debugging interrupt/resume
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.INFO)

common_instructions = (
    "Your name is Echo. You are a story teller that interacts with the user via voice."
    "You are curious and friendly, with a sense of humor."
)


@dataclass
class StoryData:
    # Shared data that's used by the storyteller agent.
    # This structure is passed as a parameter to function calls.

    name: Optional[str] = None
    location: Optional[str] = None


class IntroAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=f"{common_instructions} Your goal is to gather a few pieces of "
            "information from the user to make the story personalized and engaging."
            "You should ask the user for their name and where they are from."
            "Start the conversation with a short introduction.",
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

    @function_tool
    async def information_gathered(
        self,
        context: RunContext[StoryData],
        name: str,
        location: str,
    ):
        """Called when the user has provided the information needed to make the story
        personalized and engaging.

        Args:
            name: The name of the user
            location: The location of the user
        """

        context.userdata.name = name
        context.userdata.location = location

        story_agent = StoryAgent(name, location)
        # by default, StoryAgent will start with a new context, to carry through the current
        # chat history, pass in the chat_ctx
        # story_agent = StoryAgent(name, location, chat_ctx=self.chat_ctx)

        logger.info(
            "switching to the story agent with the provided user data: %s", context.userdata
        )
        return story_agent, "Let's start the story!"


class StoryAgent(Agent):
    def __init__(self, name: str, location: str, *, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions=f"{common_instructions}. You should use the user's information in "
            "order to make the story personalized."
            "create the entire story, weaving in elements of their information, and make it "
            "interactive, occasionally interating with the user."
            "do not end on a statement, where the user is not expected to respond."
            "when interrupted, ask if the user would like to continue or end."
            f"The user's name is {name}, from {location}.",
            # each agent could override any of the model services, including mixing
            # realtime and non-realtime models
            llm=openai.realtime.RealtimeModel(voice="echo"),
            tts=None,
            chat_ctx=chat_ctx,
        )

    async def on_enter(self):
        # when the agent is added to the session, we'll initiate the conversation by
        # using the LLM to generate a reply
        self.session.generate_reply()

    @function_tool
    async def story_finished(self, context: RunContext[StoryData]):
        """When you are fininshed telling the story (and the user confirms they don't
        want anymore), call this function to end the conversation."""
        # interrupt any existing generation
        self.session.interrupt()

        # generate a goodbye message and hang up
        # awaiting it will ensure the message is played out before returning
        await self.session.generate_reply(
            instructions=f"say goodbye to {context.userdata.name}", allow_interruptions=False
        )

        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # Configurable ignore list for soft utterances while agent is speaking.
    soft_inputs = {"yeah", "yah", "ya", "ok", "okay", "hmm", "right", "uh", "uhh", "uhhuh", "uh-huh"}
    command_keywords = {"stop", "wait", "hold", "halt", "pause", "cancel", "quit"}
    resume_keywords = {"continue", "resume", "start", "go"}
    awaiting_resume = False

    def normalize(text: str) -> list[str]:
        cleaned = re.sub(r"[^a-z\s]", " ", text.lower())
        return [w for w in cleaned.split() if w]

    def is_interrupt_command(tokens: list[str]) -> bool:
        text = " ".join(tokens)
        if "hold on" in text or "hang on" in text:
            return True
        return any(tok in command_keywords for tok in tokens)

    def is_soft_only(tokens: list[str]) -> bool:
        # treat as soft only if every token is in the soft set
        return bool(tokens) and all(tok in soft_inputs for tok in tokens)

    session = AgentSession[StoryData](
        vad=ctx.proc.userdata["vad"],
        # any combination of STT, LLM, TTS, or realtime API can be used
        llm=openai.LLM(model="gpt-4o-mini"),
        stt=deepgram.STT(model="nova-3"),
        tts=deepgram.TTS(model="aura-asteria-en"),
        userdata=StoryData(),
        # disable automatic interruptions from short utterances while the agent is speaking;
        # we handle stop/wait manually in the transcript hooks instead
        min_interruption_words=10,
    )

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    @session.on("user_input_transcribed")
    def _filter_during_playback(ev: UserInputTranscribedEvent):
        nonlocal awaiting_resume
        # only gate user speech while the agent is currently speaking
        if session.agent_state != "speaking":
            return

        tokens = normalize(ev.transcript)
        if not tokens:
            return

        if is_interrupt_command(tokens):
            logger.info(
                "interrupt keyword detected during playback", extra={"transcript": ev.transcript}
            )
            awaiting_resume = True
            logger.info("awaiting_resume set to True (user asked to interrupt)")
            # Prefer a gentle interrupt so sinks that support pause can pause playback
            # instead of force-cancelling generation. Use force=True only for hard stops.
            try:
                session.interrupt(force=False)
            except Exception:
                # fallback to force if gentle interrupt isn't supported in this runtime
                session.interrupt(force=True)
            session.clear_user_turn()
            return

        if is_soft_only(tokens):
            logger.debug(
                "ignoring soft utterance during playback", extra={"transcript": ev.transcript}
            )
            session.clear_user_turn()
            return

        # treat other speech while speaking as normal interruptible input (agent will decide)

    @session.on("user_input_transcribed")
    def _resume_if_requested(ev: UserInputTranscribedEvent):
        nonlocal awaiting_resume

        tokens = normalize(ev.transcript)
        if not tokens:
            return

        # Diagnostic: log the transcript and awaiting flag so we can trace why resume isn't firing
        logger.info(
            "resume handler invoked", extra={"transcript": ev.transcript, "awaiting_resume": awaiting_resume}
        )

        # If we're awaiting resume and the user said a resume keyword, trigger continuation.
        # Also allow a more permissive match if awaiting_resume is True (helpful for mis-transcriptions).
        is_resume = awaiting_resume and any(tok in resume_keywords for tok in tokens)
        permissive_resume = awaiting_resume and ("continue" in ev.transcript.lower() or "keep going" in ev.transcript.lower())

        if is_resume or permissive_resume:
            logger.info("resume keyword detected after stop", extra={"transcript": ev.transcript})
            awaiting_resume = False
            logger.info("awaiting_resume cleared; requesting agent to continue")
            session.clear_user_turn()
            # nudge the agent to keep going from where it stopped; ensure playback isn't interrupted
            try:
                logger.info("calling session.generate_reply for resume")
                session.generate_reply(instructions="Continue from where you left off.", allow_interruptions=False)
                logger.info("generate_reply called to continue the story")
            except Exception:
                logger.exception("failed to call generate_reply for resume; scheduling retry in 1s")
                import asyncio

                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = None

                def _retry():
                    try:
                        logger.info("retrying session.generate_reply for resume")
                        session.generate_reply(instructions="Continue from where you left off.", allow_interruptions=False)
                        logger.info("retry generate_reply called")
                    except Exception:
                        logger.exception("retry generate_reply failed")

                if loop and loop.is_running():
                    loop.call_later(1, _retry)
                else:
                    # fallback: spawn a background thread to wait and call
                    import threading, time

                    def _bg():
                        time.sleep(1)
                        _retry()

                    threading.Thread(target=_bg, daemon=True).start()

    await session.start(
        agent=IntroAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    # Auto-enable system speaker in console mode unless explicitly disabled.
    # This hooks into AgentsConsole.acquire_io so the speaker is enabled after
    # the console I/O is acquired. Set env var `LIVEKIT_CONSOLE_NO_SPEAKER=1`
    # to opt-out (useful for CI or headless machines).
    try:
        import os

        from livekit.agents.cli.cli import AgentsConsole

        _orig_acquire = AgentsConsole.acquire_io

        def _acquire_and_enable(self, *, loop: object, session: object) -> None:
            # call the original to create console IO
            _orig_acquire(self, loop=loop, session=session)

            # enable speaker unless user opted out
            if os.environ.get("LIVEKIT_CONSOLE_NO_SPEAKER"):
                return

            try:
                # best-effort: if sounddevice is missing or device inaccessible, warn and continue
                self.set_speaker_enabled(True)
            except Exception as e:  # pragma: no cover - environment-specific
                logger.warning("auto-enable speaker failed: %s", e)

        AgentsConsole.acquire_io = _acquire_and_enable
    except Exception:
        # if AgentsConsole can't be imported (unlikely), skip auto-enable
        logger.debug("AgentsConsole not available; skipping auto-enable speaker")

    cli.run_app(server)
