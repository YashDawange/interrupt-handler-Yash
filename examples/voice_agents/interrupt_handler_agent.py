import asyncio
import re
from dataclasses import dataclass
from typing import Optional

from livekit.agents import (
    Agent,
    AgentSession,
    AgentState,
    AgentStateChangedEvent,
    JobContext,
    RunContext,
    UserInputTranscribedEvent,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.agents.llm import ChatContext
from livekit.agents.pipeline.speech_handle import SpeechHandle
from livekit.plugins import deepgram, elevenlabs, openai, silero

from .interrupt_config import IGNORE_WORDS, INTERRUPT_WORDS


# ---------- helpers ----------

WORD_RE = re.compile(r"[a-zA-Z']+")


def _normalize(text: str) -> str:
    return text.strip().lower()


def _extract_words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def _contains_interrupt_word(words: list[str]) -> bool:
    for w in words:
        if w in INTERRUPT_WORDS:
            return True
    return False


def _is_pure_backchannel(words: list[str]) -> bool:
    # True if there is at least one word AND all words are ignore words
    if not words:
        return False
    return all(w in IGNORE_WORDS for w in words)


# ---------- core handler ----------

@dataclass
class BackchannelInterruptHandler:
    """
    Logic layer that:
      - Ignores soft backchannel words while the agent is speaking.
      - Interrupts immediately on command words while speaking.
      - Lets input pass through when the agent is silent.
    """

    session: AgentSession
    agent_is_speaking: bool = False

    def install(self) -> None:
        # Hook into the existing LiveKit Agent events (framework integration).
        self.session.on("agent_state_changed")(self._on_agent_state_changed)
        self.session.on("user_input_transcribed")(self._on_user_input_transcribed)

    def _on_agent_state_changed(self, event: AgentStateChangedEvent) -> None:
        # We only care whether the agent is currently speaking.
        self.agent_is_speaking = event.new_state == AgentState.SPEAKING

    def _on_user_input_transcribed(self, event: UserInputTranscribedEvent) -> None:
        # Use STT stream as suggested in the assignment (transcription logic).
        if not event.is_final:
            return

        transcript = _normalize(event.transcript)
        words = _extract_words(transcript)

        if not words:
            return

        if self.agent_is_speaking:
            self._handle_while_speaking(words)
        else:
            # When the agent is silent, we don't block anything:
            # "yeah" should be treated as a valid answer.
            return

    def _handle_while_speaking(self, words: list[str]) -> None:
        """
        Logic matrix while the agent is speaking:

          - only ignore-words  -> IGNORE (no interruption)
          - contains command   -> INTERRUPT (semantic interruption)
          - other content      -> let normal pipeline handle it
        """
        # 1) Pure backchannel: IGNORE
        if _is_pure_backchannel(words):
            # VAD may have already detected speech; we clear the turn so that
            # this doesn't become a "false" interruption (assignment hint).
            try:
                self.session.clear_user_turn()
            except Exception:
                pass
            return

        # 2) Any interrupt keyword: semantic interrupt
        if _contains_interrupt_word(words):
            self._interrupt_current_speech()
            return

        # 3) Otherwise: let LiveKit's normal interruption rules apply
        return

    def _interrupt_current_speech(self) -> None:
        """
        Stop the currently playing TTS immediately for 'stop', 'wait', etc.
        """
        handle: Optional[SpeechHandle] = self.session.current_speech
        if not handle:
            return

        try:
            handle.cancel(cancel_nested=True)
        except Exception:
            # Best-effort cancel
            pass


# ---------- Example agent to exercise the behavior ----------

class HistoryAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a patient voice assistant. "
                "When asked to explain something, you respond in long, coherent paragraphs. "
                "Do not stop mid-sentence unless explicitly asked."
            ),
            chat_ctx=ChatContext(),
        )

    @function_tool
    async def explain_world_war_two(self, context: RunContext) -> str:
        return (
            "World War Two, which took place from 1939 to 1945, was a global conflict involving "
            "many nations across Europe, Asia, Africa, and the Americas. It began with Germany's "
            "invasion of Poland, and soon expanded as alliances drew more countries into the war. "
            "The conflict was marked by devastating battles, widespread atrocities, and massive "
            "civilian casualties. Over the course of the war, key turning points included the "
            "Battle of Britain, the invasion of the Soviet Union, the Pacific island campaigns, "
            "and the D-Day landings in Normandy. Ultimately, the Axis powers were defeated, "
            "leading to the end of the war in Europe in May 1945 and in the Pacific in August 1945. "
            "The war reshaped global politics, established the United Nations, and set the stage "
            "for the Cold War between the United States and the Soviet Union."
        )

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions=(
                "Greet the user briefly, then explain a long topic using the tool "
                "'explain_world_war_two'."
            ),
            allow_interruptions=True,
        )


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    agent = HistoryAgent()

    session = AgentSession(
        vad=silero.VAD.load(),            
        stt=deepgram.STT(model="nova-3"),  
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=elevenlabs.TTS(),
    )

    await session.start(agent=agent, room=ctx.room)

    BackchannelInterruptHandler(session=session).install()

    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
