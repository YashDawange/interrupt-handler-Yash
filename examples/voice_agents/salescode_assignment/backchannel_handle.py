from dataclasses import dataclass, field
from typing import Set
from livekit.agents import AgentSession, AgentStateChangedEvent, UserInputTranscribedEvent

@dataclass
class InterruptionHandler:
    session: AgentSession

    ignore_words: Set[str] = field(default_factory=lambda: {
    # Short acknowledgements
    "yeah", "ya", "yep", "yup", "ok", "okay", "k",
    "sure", "right", "alright", "fine", "o", "oo", "ookay", "oh", "ooh",

    # Thinking sounds
    "mm", "hmm", "uh", "uhh", "huh", "mmm", "mhmm",
    "uh-huh", "mm-hmm", "uh huh", "mhm", "erm", "em",

    # Soft confirmations
    "gotcha", "got it", "i see", "i know", "true",
    "cool", "nice", "great", "okay okay",

    # Agreement / Listening cues
    "right right", "yeah yeah", "okay yep",
    "sounds good", "that's right",

    # Other neutral fillers
    "well", "like", "so", "oh", "ah", "oh okay",
    })


    command_words: Set[str] = field(default_factory=lambda: {
    # Direct interrupt commands
    "stop", "wait", "pause", "hold", "hold on", "hang on",
    "cancel", "freeze", "no", "nope", "stop stop",

    # More natural interruption phrases
    "that's enough", "enough", "just a sec", "one sec",
    "one second", "shh", "quiet", "stop talking",

    # Stronger interruptions (optional depending on assignment)
    "be quiet", "shut up"
    })


    _agent_state: str = "initializing"

    def attach(self) -> None:
        @self.session.on("agent_state_changed")
        def _(ev: AgentStateChangedEvent):
            self._agent_state = ev.new_state

        @self.session.on("user_input_transcribed")
        def _(ev: UserInputTranscribedEvent):
            text = ev.transcript.lower().strip()
            if text:
                self._process(text, ev.is_final)

    def _process(self, text: str, final: bool):
        tokens = text.split()
        speaking = self._agent_state == "speaking"

        if speaking:
            if any(t in self.command_words for t in tokens):
                return self._interrupt()
            if final:
                if all(t in self.ignore_words for t in tokens):
                    return self.session.clear_user_turn()
                return self._interrupt()
            return

        if final and all(t in self.ignore_words for t in tokens):
            return self.session.generate_reply(
                instructions=f"User said '{text}'. Treat this as confirmation and continue."
            )

    def _interrupt(self):
        for func in (self.session.interrupt, self.session.clear_user_turn):
            try:
                func(force=True) if func == self.session.interrupt else func()
            except Exception:
                pass
