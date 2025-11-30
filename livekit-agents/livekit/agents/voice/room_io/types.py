from __future__ import annotations

from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from livekit import rtc

from ...log import logger
from ...types import NOT_GIVEN, NotGivenOr
from ...utils import is_given
# add these near other imports
from interrupt_handler import decide_action
from vad_handler import VADHandler

# module-level vad handler used to track whether the agent is currently speaking
vad_handler = VADHandler()

if TYPE_CHECKING:
    from ..agent_session import AgentSession


DEFAULT_PARTICIPANT_KINDS: list[rtc.ParticipantKind.ValueType] = [
    rtc.ParticipantKind.PARTICIPANT_KIND_SIP,
    rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD,
]

DEFAULT_CLOSE_ON_DISCONNECT_REASONS: list[rtc.DisconnectReason.ValueType] = [
    rtc.DisconnectReason.CLIENT_INITIATED,
    rtc.DisconnectReason.ROOM_DELETED,
    rtc.DisconnectReason.USER_REJECTED,
]


@dataclass
class TextInputEvent:
    text: str
    info: rtc.TextStreamInfo
    participant: rtc.RemoteParticipant


TextInputCallback = Callable[
    ["AgentSession", TextInputEvent], Optional[Coroutine[None, None, None]]
]


@dataclass
class NoiseCancellationParams:
    participant: rtc.Participant
    track: rtc.Track


NoiseCancellationSelector = Callable[
    [NoiseCancellationParams], Optional[rtc.NoiseCancellationOptions]
]

def _default_text_input_cb(sess: "AgentSession", ev: TextInputEvent):
    """
    Default handler for text input events.

    Integration:
      - Uses decide_action(vad_handler.agent_speaking, text)
      - If action == "ignore": do nothing (user said filler while agent speaking)
      - If action == "interrupt": stop agent playback and acknowledge
      - If action == "respond": forward to normal reply generation
    """

    text = (ev.text or "").strip()
    if text == "":
        return None

    # Decide based on whether the agent is speaking right now.
    action = decide_action(vad_handler.agent_speaking, text)
    logger.debug(f"[interrupt] participant={getattr(ev.participant, 'sid', 'unknown')} text='{text}' -> action={action}")

    if action == "ignore":
        # Agent is speaking and user said only filler tokens: ignore.
        # Do not interrupt or generate any reply.
        return None

    if action == "interrupt":
        # User explicitly asked to stop/wait - interrupt ongoing agent playback.
        # sess.interrupt() is the starter's API that attempts to stop generation/playback.
        try:
            sess.interrupt()
        except Exception:
            logger.debug("interrupt call failed (but continuing)")

        # If the starter has an explicit "stop playback" API you can call it here.
        # e.g. if the session provides sess.stop_playback() use that before generating an ack.
        # NOTE: Many starter implementations run generate_reply as the default reply mechanism.
        # For a short acknowledgement, you can use generate_reply with a small prompt or
        # implement a dedicated play_tts method if present.
        ack_text = "Okay, I stopped. What would you like?"
        # Return the coroutine so the starter will run it.
        return sess.generate_reply(user_input=ack_text)

    # action == "respond"
    # Agent is silent or user said meaningful content -> treat as normal user input.
    return sess.generate_reply(user_input=text)



@dataclass
class TextInputOptions:
    text_input_cb: TextInputCallback = _default_text_input_cb


@dataclass
class AudioInputOptions:
    sample_rate: int = 24000
    num_channels: int = 1
    frame_size_ms: int = 50
    """The frame size in milliseconds for the audio input."""
    noise_cancellation: rtc.NoiseCancellationOptions | NoiseCancellationSelector | None = None
    pre_connect_audio: bool = True
    """Pre-connect audio enabled or not."""
    pre_connect_audio_timeout: float = 3.0
    """The pre-connect audio will be ignored if it doesn't arrive within this time."""


@dataclass
class VideoInputOptions:
    pass


@dataclass
class AudioOutputOptions:
    sample_rate: int = 24000
    num_channels: int = 1
    track_publish_options: rtc.TrackPublishOptions = field(
        default_factory=lambda: rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    track_name: NotGivenOr[str] = NOT_GIVEN
    """The name of the audio track to publish. If not provided, default to "roomio_audio"."""


@dataclass
class TextOutputOptions:
    sync_transcription: NotGivenOr[bool] = NOT_GIVEN
    """False to disable transcription synchronization with audio output.
    Otherwise, transcription is emitted as quickly as available."""
    transcription_speed_factor: float = 1.0
    """Speed factor of transcription synchronization with audio output.
    Only effective if `sync_transcription` is True."""


@dataclass
class RoomOptions:
    text_input: NotGivenOr[TextInputOptions | bool] = NOT_GIVEN
    """The text input options. If not provided, default to True."""
    audio_input: NotGivenOr[AudioInputOptions | bool] = NOT_GIVEN
    """The audio input options. If not provided, default to True."""
    video_input: NotGivenOr[VideoInputOptions | bool] = NOT_GIVEN
    """The video input options. If not provided, default to False."""
    audio_output: NotGivenOr[AudioOutputOptions | bool] = NOT_GIVEN
    """The audio output options. If not provided, default to True."""
    text_output: NotGivenOr[TextOutputOptions | bool] = NOT_GIVEN
    """The transcription output options. If not provided, default to True."""

    participant_kinds: NotGivenOr[list[rtc.ParticipantKind.ValueType]] = NOT_GIVEN
    """Participant kinds accepted for auto subscription. If not provided,
    accept `DEFAULT_PARTICIPANT_KINDS`."""
    participant_identity: NotGivenOr[str] = NOT_GIVEN
    """The participant to link to. If not provided, link to the first participant.
    Can be overridden by the `participant` argument of RoomIO constructor or `set_participant`."""
    close_on_disconnect: bool = True
    """Close the AgentSession if the linked participant disconnects with reasons in
    CLIENT_INITIATED, ROOM_DELETED, or USER_REJECTED."""
    delete_room_on_close: bool = False
    """Delete the room when the AgentSession is closed, default to False"""

    def get_text_input_options(self) -> TextInputOptions | None:
        if isinstance(self.text_input, TextInputOptions):
            return self.text_input
        # if text_input is not given, default to enabled
        return TextInputOptions() if self.text_input is not False else None

    def get_audio_input_options(self) -> AudioInputOptions | None:
        if isinstance(self.audio_input, AudioInputOptions):
            return self.audio_input
        # if audio_input is not given, default to enabled
        return AudioInputOptions() if self.audio_input is not False else None

    def get_video_input_options(self) -> VideoInputOptions | None:
        if isinstance(self.video_input, VideoInputOptions):
            return self.video_input
        # if video_input is not given, default to disabled
        return VideoInputOptions() if self.video_input is True else None

    def get_audio_output_options(self) -> AudioOutputOptions | None:
        if isinstance(self.audio_output, AudioOutputOptions):
            return self.audio_output
        return AudioOutputOptions() if self.audio_output is not False else None

    def get_text_output_options(self) -> TextOutputOptions | None:
        if isinstance(self.text_output, TextOutputOptions):
            return self.text_output
        return TextOutputOptions() if self.text_output is not False else None

    @classmethod
    def _ensure_options(
        cls,
        options: NotGivenOr[RoomOptions],
        *,
        room_input_options: NotGivenOr[RoomInputOptions] = NOT_GIVEN,
        room_output_options: NotGivenOr[RoomOutputOptions] = NOT_GIVEN,
    ) -> RoomOptions:
        if is_given(room_input_options) or is_given(room_output_options):
            logger.warning(
                "RoomInputOptions and RoomOutputOptions are deprecated, use RoomOptions instead"
            )
            if not is_given(options):
                return cls._create_from_legacy(room_input_options, room_output_options)

        if isinstance(options, RoomOptions):
            return options
        else:
            return cls()

    @classmethod
    def _create_from_legacy(
        cls,
        input_options: NotGivenOr[RoomInputOptions],
        output_options: NotGivenOr[RoomOutputOptions],
    ) -> RoomOptions:
        opts = cls()
        if input_options:
            opts.text_input = (
                TextInputOptions(text_input_cb=input_options.text_input_cb)
                if input_options.text_enabled is not False
                else False
            )
            opts.audio_input = (
                AudioInputOptions(
                    sample_rate=input_options.audio_sample_rate,
                    num_channels=input_options.audio_num_channels,
                    frame_size_ms=input_options.audio_frame_size_ms,
                    noise_cancellation=input_options.noise_cancellation,
                    pre_connect_audio=input_options.pre_connect_audio,
                    pre_connect_audio_timeout=input_options.pre_connect_audio_timeout,
                )
                if input_options.audio_enabled is not False
                else False
            )
            opts.video_input = input_options.video_enabled

            opts.participant_kinds = input_options.participant_kinds
            opts.participant_identity = input_options.participant_identity
            opts.close_on_disconnect = input_options.close_on_disconnect
            opts.delete_room_on_close = input_options.delete_room_on_close

        if output_options:
            opts.audio_output = (
                AudioOutputOptions(
                    sample_rate=output_options.audio_sample_rate,
                    num_channels=output_options.audio_num_channels,
                    track_publish_options=output_options.audio_publish_options,
                    track_name=output_options.audio_track_name,
                )
                if output_options.audio_enabled is not False
                else False
            )
            opts.text_output = (
                TextOutputOptions(
                    sync_transcription=output_options.sync_transcription,
                    transcription_speed_factor=output_options.transcription_speed_factor,
                )
                if output_options.transcription_enabled is not False
                else False
            )
        return opts


# RoomInputOptions and RoomOutputOptions are deprecated


@dataclass
class RoomInputOptions:
    text_enabled: NotGivenOr[bool] = NOT_GIVEN
    """If not given, default to True."""
    audio_enabled: NotGivenOr[bool] = NOT_GIVEN
    """If not given, default to True."""
    video_enabled: NotGivenOr[bool] = NOT_GIVEN
    """If not given, default to False."""
    audio_sample_rate: int = 24000
    audio_num_channels: int = 1
    audio_frame_size_ms: int = 50
    """The frame size in milliseconds for the audio input."""
    noise_cancellation: rtc.NoiseCancellationOptions | None = None
    text_input_cb: TextInputCallback = _default_text_input_cb
    participant_kinds: NotGivenOr[list[rtc.ParticipantKind.ValueType]] = NOT_GIVEN
    """Participant kinds accepted for auto subscription. If not provided,
    accept `DEFAULT_PARTICIPANT_KINDS`."""
    participant_identity: NotGivenOr[str] = NOT_GIVEN
    """The participant to link to. If not provided, link to the first participant.
    Can be overridden by the `participant` argument of RoomIO constructor or `set_participant`."""
    pre_connect_audio: bool = True
    """Pre-connect audio enabled or not."""
    pre_connect_audio_timeout: float = 3.0
    """The pre-connect audio will be ignored if it doesn't arrive within this time."""
    close_on_disconnect: bool = True
    """Close the AgentSession if the linked participant disconnects with reasons in
    CLIENT_INITIATED, ROOM_DELETED, or USER_REJECTED."""
    delete_room_on_close: bool = False
    """Delete the room when the AgentSession is closed, default to False"""


@dataclass
class RoomOutputOptions:
    transcription_enabled: NotGivenOr[bool] = NOT_GIVEN
    """If not given, default to True."""
    audio_enabled: NotGivenOr[bool] = NOT_GIVEN
    """If not given, default to True."""
    audio_sample_rate: int = 24000
    audio_num_channels: int = 1
    audio_publish_options: rtc.TrackPublishOptions = field(
        default_factory=lambda: rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    audio_track_name: NotGivenOr[str] = NOT_GIVEN
    """The name of the audio track to publish. If not provided, default to "roomio_audio"."""
    sync_transcription: NotGivenOr[bool] = NOT_GIVEN
    """False to disable transcription synchronization with audio output.
    Otherwise, transcription is emitted as quickly as available."""
    transcription_speed_factor: float = 1.0
    """Speed factor of transcription synchronization with audio output.
    Only effective if `sync_transcription` is True."""


# DEFAULT_ROOM_INPUT_OPTIONS = RoomInputOptions()
# DEFAULT_ROOM_OUTPUT_OPTIONS = RoomOutputOptions()
