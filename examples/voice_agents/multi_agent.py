import logging
logging.basicConfig(level=logging.DEBUG)
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
from livekit.plugins import google
from livekit.plugins import silero

logger = logging.getLogger("multi-agent")

load_dotenv()

common_instructions = (
    "Your name is Echo. You are a story teller that interacts with the user via voice."
    "You are curious and friendly, with a sense of humor."
)


@dataclass
class StoryData:
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

        logger.info(
            "switching to the story agent with the provided user data: %s", context.userdata
        )
        return story_agent, "Let's start the story!"


class StoryAgent(Agent):
    def __init__(self, name: str, location: str, *, chat_ctx: Optional[ChatContext] = None) -> None:
        super().__init__(
            instructions=f"{common_instructions}. You should use the user's information in "
            "order to make the story personalized. "
            "create the entire story, weaving in elements of their information, and make it "
            "interactive, occasionally interacting with the user. "
            "do not end on a statement, where the user is not expected to respond. "
            "when interrupted, ask if the user would like to continue or end. "
            f"The user's name is {name}, from {location}.",
            llm=google.LLM(model="gemini-2.0-flash"),
            tts=deepgram.TTS(model="aura-asteria-en"),
            chat_ctx=chat_ctx,
        )

    async def on_enter(self):
        self.session.generate_reply()

    @function_tool
    async def story_finished(self, context: RunContext[StoryData]):
        """When you are finished telling the story (and the user confirms they don't
        want anymore), call this function to end the conversation."""
        self.session.interrupt()

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
        return bool(tokens) and all(tok in soft_inputs for tok in tokens)

    session = AgentSession[StoryData](
        vad=ctx.proc.userdata["vad"],
        llm=google.LLM(model="gemini-2.0-flash"),
        stt=deepgram.STT(model="nova-3"),
        tts=deepgram.TTS(model="aura-asteria-en"),
        userdata=StoryData(),
        min_interruption_words=10,
    )

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
            session.interrupt(force=True)
            return

        if is_soft_only(tokens):
            logger.debug(
                "ignoring filler utterance during playback", extra={"transcript": ev.transcript}
            )
            session.clear_user_turn()
            return

    @session.on("user_input_transcribed")
    def _resume_if_requested(ev: UserInputTranscribedEvent):
        nonlocal awaiting_resume

        if session.agent_state == "speaking":
            return

        tokens = normalize(ev.transcript)
        if not tokens:
            return

        if awaiting_resume and any(tok in resume_keywords for tok in tokens):
            logger.info("resume keyword detected after stop", extra={"transcript": ev.transcript})
            awaiting_resume = False
            session.clear_user_turn()
            session.generate_reply()

    await session.start(
        agent=IntroAgent(),
        room=ctx.room,
    )

if __name__ == "__main__":
    cli.run_app(server)