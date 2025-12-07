
import logging
import asyncio

from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    UserInputTranscribedEvent,
    AgentStateChangedEvent,
    UserStateChangedEvent,
)
from interruption_handler import AgentSpeechState, classify_user_text

logger = logging.getLogger("interrupt-handler-agent")

load_dotenv()

server = AgentServer()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Your name is Kelly. You interact with users via voice. "
                "Keep your responses concise and to the point. "
                "Do not use emojis, asterisks, markdown, or any special characters. "
                "You are curious, friendly, and have a sense of humor. "
                "You speak English to the user. "

                # Behavioral constraints for backchannels vs interruptions:
                "When you are explaining something and the user says short acknowledgement "
                "words like 'yeah', 'ok', 'okay', 'uh-huh', 'hmm', 'right', etc., you must "
                "IGNORE them completely and keep talking as if they were never said. "
                "Do NOT change topic, do NOT ask follow-up questions, and do NOT react to them "
                "while you are mid-explanation. "

                "Only treat such acknowledgement words as meaningful answers when you are silent "
                "and have asked a question like 'Are you ready?' or 'Should I continue?'. "
                "If the user clearly says interruption commands like 'stop', 'wait', or 'no' "
                "while you are speaking, you must stop immediately and then wait silently for "
                "further user input."
            ),
        )

    async def on_enter(self):
        # initial reply; we do not allow auto interruptions here
        await self.session.generate_reply(allow_interruptions=False)


def prewarm(proc: JobProcess):
    # No VAD or silero here to avoid onnxruntime DLL issues
    proc.userdata["vad"] = None


server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # --- Create AgentSession with manual interruption handling ---
    session = AgentSession(
        # STT: streaming, via LiveKit Inference (Deepgram)
        stt="deepgram/nova-3",
        # LLM: use OpenAI (your env must have OPENAI_API_KEY)
        llm="openai/gpt-4.1-mini",
        # TTS: Cartesia voice
        tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",

        # Use STT-based turn detection to get streaming transcripts
        turn_detection="stt",

        # We handle interruptions ourselves
        allow_interruptions=False,
        preemptive_generation=True,
    )

    # --------------------------
    # Conversation state
    # --------------------------
    agent_speech_state: AgentSpeechState = AgentSpeechState.SILENT
    pending_interrupt: bool = False  # user started speaking while agent is speaking

    # --------------------------
    # Event handlers
    # --------------------------

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        """
        Map detailed agent state to our simpler SPEAKING / SILENT.
        Possible states include: 'initializing', 'idle', 'listening', 'thinking', 'speaking'.
        """
        nonlocal agent_speech_state

        if ev.new_state == "speaking":
            agent_speech_state = AgentSpeechState.SPEAKING
        else:
            agent_speech_state = AgentSpeechState.SILENT

    @session.on("user_state_changed")
    def _on_user_state_changed(ev: UserStateChangedEvent):
        """
        When the user starts speaking while the agent is speaking, mark a candidate interruption.
        """
        nonlocal pending_interrupt, agent_speech_state

        if ev.new_state == "speaking" and agent_speech_state == AgentSpeechState.SPEAKING:
            pending_interrupt = True

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        """
        Called whenever we get user transcription.
        We:
          - only act on final transcripts
          - classify them as IGNORE / INTERRUPT / RESPOND
          - decide whether to stop speech and/or generate a reply
        """
        nonlocal pending_interrupt, agent_speech_state

        if not ev.is_final:
            # only decide on final text
            return

        text = (ev.transcript or "").strip()
        if not text:
            return

        decision = classify_user_text(text, agent_speech_state)

        # -----------------------
        # Case 1: agent speaking
        # -----------------------
        if agent_speech_state == AgentSpeechState.SPEAKING:
            if decision == "IGNORE":
                # Scenario 1: Long explanation + "yeah / ok / uh-huh"
                # => do nothing, keep speaking seamlessly
                pending_interrupt = False
                return

            if decision == "INTERRUPT":
                # Scenario 3 & 4: "no stop", "yeah okay but wait"
                async def _do_hard_interrupt() -> None:
                    nonlocal pending_interrupt
                    # Always interrupt, even if pending_interrupt is False
                    await session.interrupt()
                    pending_interrupt = False
                    # HARD STOP requirement:
                    # Do NOT generate any reply here.
                    # Agent should stay silent until the user speaks again.

                asyncio.create_task(_do_hard_interrupt())
                return

        # -----------------------
        # Case 2: agent silent
        # -----------------------
        if agent_speech_state == AgentSpeechState.SILENT and decision == "RESPOND":
            # Scenario 2: Agent asks "Are you ready?" and goes silent, user says "yeah"
            async def _reply() -> None:
                await session.generate_reply(
                    user_input=text,
                    allow_interruptions=False,
                )

            asyncio.create_task(_reply())

    # --------------------------
    # Start the session
    # --------------------------

    await ctx.connect()

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)
