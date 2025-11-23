import asyncio
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
from typing import Any
from livekit.agents import llm, types
from livekit.agents.llm import function_tool
from livekit.plugins import silero


# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

load_dotenv()


class MockLLM(llm.LLM):
    def __init__(self):
        super().__init__()

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.FunctionTool | llm.RawFunctionTool] | None = None,
        conn_options: types.APIConnectOptions = types.DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: types.NotGivenOr[bool] = types.NOT_GIVEN,
        tool_choice: types.NotGivenOr[llm.ToolChoice] = types.NOT_GIVEN,
        extra_kwargs: types.NotGivenOr[dict[str, Any]] = types.NOT_GIVEN,
    ) -> llm.LLMStream:
        return MockLLMStream(self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options)

class MockLLMStream(llm.LLMStream):
    def __init__(self, llm: llm.LLM, chat_ctx: llm.ChatContext, **kwargs):
        super().__init__(llm, chat_ctx=chat_ctx, **kwargs)
        self._chat_ctx = chat_ctx

    async def _run(self) -> None:
        last_user_msg = ""
        # Check if chat_ctx has messages attribute and if it is not empty
        logger.info(f"MockLLM: chat_ctx type: {type(self._chat_ctx)}")
        logger.info(f"MockLLM: has messages attr: {hasattr(self._chat_ctx, 'messages')}")
        
        if hasattr(self._chat_ctx, "messages") and self._chat_ctx.messages:
            last_user_msg = self._chat_ctx.messages[-1].content
            logger.info(f"MockLLM: last_user_msg (raw): {last_user_msg}")
        else:
            logger.info(f"MockLLM: No messages found, checking items...")
            if hasattr(self._chat_ctx, "items") and self._chat_ctx.items:
                last_item = self._chat_ctx.items[-1]
                logger.info(f"MockLLM: last item: {last_item}")
                if hasattr(last_item, "content"):
                    last_user_msg = last_item.content
                    logger.info(f"MockLLM: last_user_msg from items: {last_user_msg}")
        
        if isinstance(last_user_msg, list):
             last_user_msg = " ".join([c for c in last_user_msg if isinstance(c, str)])
        
        logger.info(f"MockLLM: final last_user_msg: '{last_user_msg}'")
        
        text = "This is a mock response to test the interruption logic. I will keep speaking so you can try to interrupt me. Say yeah or ok to see if I ignore it. Say stop to see if I stop."
        
        if "story" in str(last_user_msg).lower():
            logger.info("MockLLM: STORY MODE ACTIVATED!")
            text = "Once upon a time, in a land far, far away, there was a brave little agent who wanted to learn how to speak. It tried very hard to understand humans. It learned to listen, to speak, and even to ignore simple words like yeah and ok. It was a very smart agent indeed. " * 3
        elif any(cmd in str(last_user_msg).lower() for cmd in ["stop", "wait", "no"]):
            text = "Stopping."

        for word in text.split():
            chunk = llm.ChatChunk(
                id="mock-id",
                delta=llm.ChoiceDelta(content=word + " ")
            )
            await self._event_ch.send(chunk)
            await asyncio.sleep(0.05) # Small delay for TTS stability

class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your name is Kelly. You would interact with users via voice."
            "with that in mind keep your responses concise and to the point."
            "do not use emojis, asterisks, markdown, or other special characters in your responses."
            "You are curious and friendly, and have a sense of humor."
            "you will speak english to the user",
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply()

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(
        self, context: RunContext, location: str, latitude: str, longitude: str
    ):
        """Called when the user asks for weather related information.
        Ensure the user's location (city or region) is provided.
        When given a location, please estimate the latitude and longitude of the location and
        do not ask the user for them.

        Args:
            location: The location they are asking for
            latitude: The latitude of the location, do not ask user for it
            longitude: The longitude of the location, do not ask user for it
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt="deepgram/nova-3",
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        # llm="openai/gpt-4.1-mini",
        llm=MockLLM(),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
        # when it's detected, you may resume the agent's speech
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
        # CRITICAL: Set min_interruption_words to 1 to enable intelligent interruption logic
        min_interruption_words=1,
        ignored_words=["yeah", "ok", "okay", "hmm", "right", "uh-huh", "uhuh"],
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

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # uncomment to enable the Krisp BVC noise cancellation
                # noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
