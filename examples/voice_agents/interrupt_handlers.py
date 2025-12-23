import logging
from typing import TYPE_CHECKING

from livekit.agents import AgentStateChangedEvent, UserInputTranscribedEvent
from interrupt_config import contains_strong_interrupt, is_soft_backchannel

if TYPE_CHECKING:
    from livekit.agents import AgentSession

logger = logging.getLogger("basic-agent")


def attach_interrupt_handlers(session: "AgentSession") -> None:
    agent_is_speaking = {"value": False}

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev: AgentStateChangedEvent):
        agent_is_speaking["value"] = ev.new_state == "speaking"
        logger.debug("Agent state changed: %s -> %s", ev.old_state, ev.new_state)

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev: UserInputTranscribedEvent):
        text = (ev.transcript or "").strip()
        if not text:
            return

        if not agent_is_speaking["value"]:
            logger.debug(
                "User speaking while agent not speaking: %r (final=%s)",
                text,
                ev.is_final,
            )
            return

        if not ev.is_final:
            logger.debug("Interim transcript while speaking (ignored for logic): %r", text)
            return

        logger.info("User spoke while agent is speaking: %r", text)

        if is_soft_backchannel(text):
            logger.info("Ignoring soft backchannel while agent is speaking: %r", text)
            session.clear_user_turn()
            return

        if contains_strong_interrupt(text):
            logger.info("Detected strong interrupt while agent speaking. Interrupting: %r", text)
            session.interrupt(force=True)
            return

        logger.info("Detected mixed/non-soft input while speaking. Interrupting: %r", text)
        session.interrupt(force=True)
