"""
Smart Interruption Agent Activity

This module extends AgentActivity to override interruption hooks and integrate
the smart interruption filter. It delays interruption decisions until STT
transcripts are available for classification.
"""

import logging
from typing import Optional

from .. import stt, vad
from .agent_activity import AgentActivity
from .events import UserInputTranscribedEvent
from .smart_interruption import SmartInterruptionFilter

logger = logging.getLogger(__name__)


class SmartInterruptionAgentActivity(AgentActivity):
    """
    AgentActivity with smart interruption filtering.

    This class overrides the VAD and transcript event handlers to delay
    interruption decisions until transcripts can be classified as either
    backchannel feedback or explicit interruptions.
    """

    def __init__(
        self,
        *args,
        smart_filter: Optional[SmartInterruptionFilter] = None,
        **kwargs,
    ):
        """
        Initialize smart interruption activity.

        Args:
            smart_filter: Optional SmartInterruptionFilter instance
            *args, **kwargs: Passed to parent AgentActivity
        """
        super().__init__(*args, **kwargs)
        self._smart_filter = smart_filter or SmartInterruptionFilter()
        logger.info(
            "SmartInterruptionAgentActivity initialized",
            extra={"filter_enabled": self._smart_filter is not None},
        )

    async def start(self) -> None:
        """Override start to patch audio recognition after it's created."""
        await super().start()
        
        # Now that _audio_recognition is created, patch it
        if self._audio_recognition:
            self._patch_audio_recognition()
            logger.info("Smart interruption: audio recognition patched")

    def _patch_audio_recognition(self) -> None:
        """Monkey-patch the audio recognition's STT event handler to filter backchannels."""
        original_on_stt_event = self._audio_recognition._on_stt_event
        
        async def filtered_on_stt_event(ev: stt.SpeechEvent) -> None:
            """Intercept STT events and filter backchannels before they reach audio_recognition."""
            # Check if this is a final transcript during agent speech
            if (
                ev.type == stt.SpeechEventType.FINAL_TRANSCRIPT
                and ev.alternatives
                and self._session.agent_state == "speaking"
            ):
                transcript = ev.alternatives[0].text
                should_interrupt = self._smart_filter.should_interrupt(
                    transcript=transcript,
                    agent_is_speaking=True,
                    is_final=True,
                )
                
                if not should_interrupt:
                    # It's a backchannel - completely skip processing
                    logger.info(
                        "Smart interruption: backchannel filtered at STT level",
                        extra={"transcript": transcript},
                    )
                    return  # Don't call original handler - event is dropped
            
            # Not a backchannel or agent not speaking - process normally
            await original_on_stt_event(ev)
        
        # Replace the method
        self._audio_recognition._on_stt_event = filtered_on_stt_event

    def _interrupt_by_audio_activity(self) -> None:
        """
        Override to completely block all VAD-based interruptions.
        
        This method is called from multiple places in the parent:
        1. on_vad_inference_done (line 1244)
        2. on_interim_transcript (line 1264) 
        3. on_final_transcript (line 1295)
        
        By completely overriding all three callers AND this method, we ensure
        no VAD-based pause ever occurs. All interruption decisions are made
        in our on_final_transcript based on transcript classification.
        """
        # Do nothing - all interruption logic handled in on_final_transcript
        pass

    def on_vad_inference_done(self, event: vad.VADEvent) -> None:
        """
        Override VAD inference handler - completely bypass when smart filtering is active.
        
        When smart filtering is enabled, we handle ALL interruption logic through
        on_final_transcript. This prevents any VAD-based interruption pauses.

        Args:
            event: VAD event
        """
        # Only log when actual speech is detected during agent speaking
        if (
            event.speaking
            and event.speech_duration >= self._session.options.min_interruption_duration
            and self._session.agent_state == "speaking"
        ):
            logger.debug(
                "Smart interruption: speech detected during agent output",
                extra={"speech_duration": event.speech_duration},
            )
        
        # With smart filtering enabled, NEVER call parent
        # This prevents _interrupt_by_audio_activity from being called via parent's on_vad_inference_done

    def on_interim_transcript(self, ev: stt.SpeechEvent, *, speaking: bool | None) -> None:
        """
        Override interim transcript handler to bypass parent's _interrupt_by_audio_activity call.
        
        The parent's on_interim_transcript (line 1264) calls _interrupt_by_audio_activity().
        When smart filtering is active and agent is speaking, we skip emitting the event
        to prevent any pipeline reactions that might cause audio disruption.

        Args:
            ev: Speech event with interim transcript
            speaking: Whether agent is currently speaking
        """
        agent_is_speaking = self._session.agent_state == "speaking"
        
        # If agent is speaking, don't emit interim transcripts at all
        # This prevents any pipeline reactions that might disrupt audio
        if agent_is_speaking and self._smart_filter:
            return
        
        # If agent not speaking, emit the event normally
        if ev.alternatives:
            self._session.emit(
                "user_transcript_available",
                UserInputTranscribedEvent(
                    language=ev.alternatives[0].language,
                    transcript=ev.alternatives[0].text,
                    is_final=False,
                    speaker_id=ev.alternatives[0].speaker_id,
                ),
            )

    def on_final_transcript(self, ev: stt.SpeechEvent, *, speaking: bool | None = None) -> None:
        """
        Override final transcript handler to apply smart filtering.

        When agent is speaking, classify the transcript to decide whether to:
        1. Ignore it completely (backchannel) - do nothing at all
        2. Interrupt agent speech (explicit interruption) - call parent to handle
        3. Process normally (agent not speaking) - call parent to handle

        Args:
            ev: Speech event with final transcript
            speaking: Whether agent is currently speaking
        """
        if not ev.alternatives:
            super().on_final_transcript(ev, speaking=speaking)
            return
            
        transcript = ev.alternatives[0].text
        agent_is_speaking = self._session.agent_state == "speaking"
        
        # If agent is speaking, classify the transcript
        if agent_is_speaking and self._smart_filter:
            should_interrupt = self._smart_filter.should_interrupt(
                transcript=transcript,
                agent_is_speaking=True,
                is_final=True,
            )
            
            if not should_interrupt:
                # It's a backchannel - do NOTHING
                # Don't call parent, don't process, just ignore completely
                logger.info(
                    "Smart interruption: backchannel ignored completely",
                    extra={"transcript": transcript},
                )
                # Just return - don't call parent, don't do anything
                # The transcript will NOT be added to audio_recognition's _audio_transcript
                # because we're returning BEFORE audio_recognition.py line 368 executes
                # Wait - that's wrong, we're IN the hook, audio_recognition continues after we return
                #
                # Actually the issue is: audio_recognition.py extracts transcript BEFORE calling us
                # So we need to prevent it from continuing AFTER our hook returns
                # The only way is to NOT RETURN to the caller
                #
                # Since we can't prevent the caller from continuing, we need to rely on
                # the fact that we already cleared ev.alternatives[0].text
                # But that doesn't work because transcript is a local variable
                #
                # SOLUTION: Modify the event to have empty alternatives list
                ev.alternatives = []
                return
            else:
                # Real interruption - let parent handle it
                logger.info(
                    "Smart interruption: allowing real interruption",
                    extra={"transcript": transcript},
                )
        
        # For real interruptions or when agent not speaking, call parent for normal processing
        super().on_final_transcript(ev, speaking=speaking)
